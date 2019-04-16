"""Avro serialization and schema management for templatebot.* schemas.
"""

__all__ = ('Serializer',)

import functools
import json
from pathlib import Path

import structlog
import fastavro
from kafkit.registry.serializer import PolySerializer
import kafkit.registry.errors


class Serializer:
    """An Avro (Confluent Wire Format) serializer.

    Always use the `Serializer.setup` method to create a
    serializer instance.

    Parameters
    ----------
    registry : `kafkit.registry.serializer.PolySerializer`
        Client for the Confluent Schema Registry.
    logger
        Logger instance.
    staging_version `str`, optional
        If the application is running in a staging environment, this is the
        name of the staging version. This should be set through the
        ``templatebot/topicsVersion`` configuration key on the app. Leave as
        `None` if the application is not in staging.
    """

    def __init__(self, *, serializer, logger, staging_version=None):
        self._serializer = serializer
        self._logger = logger
        self._staging_version = staging_version

    @classmethod
    async def setup(cls, *, registry, app):
        """Create a `Serializer` while also registering the schemas and
        configuring the associated subjects in the Schema Registry.

        Parameters
        ----------
        registry : `kafkit.registry.aiohttp.RegistryApi`
            A Schema Registry client.
        app : `aiohttp.web.Application`
            The application instance.

        Returns
        -------
        serializer : `Serializer`
            An instance of the serializer.
        """
        logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])

        logger.debug('all schemas', schemas=list_schemas())
        for event_type in list_schemas():
            schema = load_schema(
                event_type,
                suffix=app['root']['templatebot/topicsVersion'])
            await register_schema(registry, schema, app)

        serializer = PolySerializer(registry=registry)

        return cls(
            serializer=serializer,
            logger=logger,
            staging_version=app['root']['templatebot/topicsVersion'])

    async def serialize(self, schema_name, message):
        """Serialize a Slack event.

        Parameters
        ----------
        message : `dict`
            The JSON payload for the message.

        Returns
        -------
        data : `bytes
            Data encoded in the Confluent Wire Format, ready to be sent to a
            Kafka broker.
        """
        schema = load_schema(schema_name,
                             suffix=self._staging_version)
        return await self._serializer.serialize(message, schema=schema)


@functools.lru_cache()
def load_schema(name, suffix=None):
    """Load an Avro schema from the local app data.

    This function is memoized so that repeated calls are fast.

    Parameters
    ----------
    name : `str`
        Name of the schema. This should be a fully-qualified name that matches
        the file name of schemas in the ``schemas/`` directory of the source
        repository.
    suffix : `str`, optional
        A suffix to add to the schema's name. This is typically used to create
        "staging" schemas, therefore "staging subjects" in the Schema Registry.

    Returns
    -------
    schema : `dict`
        A schema object.
    """
    schemas_dir = Path(__file__).parent / 'schemas'
    schema_path = schemas_dir / f'{name}.json'

    schema = json.loads(schema_path.read_text())

    if suffix:
        schema['name'] = '_'.join((schema['name'], suffix))

    return fastavro.parse_schema(schema)


@functools.lru_cache()
def list_schemas():
    """List the schemas in the local package.

    Returns
    -------
    events : `list` [`str`]
        List of names of schemas.

    Notes
    -----
    This function looks for schema json files in the
    ``tempaltebot/events/schemas/events`` directory of the package.

    This function is cached, so repeated calls consume no additional IO.
    """
    schemas_dir = Path(__file__).parent / 'schemas'
    schema_paths = schemas_dir.glob('*.json')
    return [p.stem for p in schema_paths]


async def register_schema(registry, schema, app):
    """Register a schema and configure subject compatibility.

    Parameters
    ----------
    registry : `kafkit.registry.aiohttp.RegistryApi`
        A Schema Registry client.
    schema : `dict`
        The Avro schema. Note that the schema should already be versioned with
        a staging suffix, if necessary.
    app : `aiohttp.web.Application` or `dict`
        The application instance, or the application's config dictionary.

    Notes
    -----
    This function registers a schema, and then ensures that the associated
    subject in the Schema Registry has the appropriate compatibility level.
    See `get_desired_compatibility`.
    """
    # TODO This function is lifted from sqrbot-jr. Add it to Kafkit?
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])

    desired_compat = get_desired_compatibility(app)

    schema_id = await registry.register_schema(schema)
    logger.info('Registered schema', subject=schema['name'], id=schema_id)

    subjects = await registry.get('/subjects')
    logger.info('All subjects', subjects=subjects)

    subject_name = schema['name']

    try:
        subject_config = await registry.get(
            '/config{/subject}',
            url_vars={'subject': subject_name})
    except kafkit.registry.errors.RegistryBadRequestError:
        logger.info('No existing configuration for this subject.',
                    subject=subject_name)
        # Create a mock config that forces a reset
        subject_config = {
            'compatibilityLevel': None
        }

    logger.info('Current subject config', config=subject_config)
    if subject_config['compatibilityLevel'] != desired_compat:
        await registry.put(
            '/config{/subject}',
            url_vars={'subject': subject_name},
            data={'compatibility': desired_compat})
        logger.info(
            'Reset subject compatibility level',
            subject=schema['name'],
            compatibility_level=desired_compat)
    else:
        logger.info(
            'Existing subject compatibility level is good',
            subject=schema['name'],
            compatibility_level=subject_config['compatibilityLevel'])


def get_desired_compatibility(app):
    """Get the desired compatibility configuration for subjects given the
    application configuration.

    Parameters
    ----------
    app : `aiohttp.web.Application`
        The application instance.

    Returns
    -------
    compatibility : `str`
        The Schema Registry compatibility level. The value is one of:

        ``"NONE"``
            If the ``templatebot/topicsVersion`` app config is set, then no
            compatiblility is required on the subject since it's a
            "staging" subject used for testing.
        ``"FORWARD_TRANSITIVE"``
            If ``templatebot/topicsVersion`` app config **is not** set, then
            the subjects must have ``"FORWARD_TRANSITIVE"`` compatibility,
            following the SQuaRE Events best practices.
    """
    if app['root']['templatebot/topicsVersion'] == '':
        return 'FORWARD_TRANSITIVE'
    else:
        return 'NONE'
