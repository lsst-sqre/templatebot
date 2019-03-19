"""Application factory for the aiohttp.web-based app.
"""

__all__ = ('create_app',)

from pathlib import Path
import logging
import sys

from aiohttp import web, ClientSession
import structlog
from kafkit.registry.aiohttp import RegistryApi

from .config import create_config
from .routes import init_root_routes, init_routes
from .middleware import setup_middleware
from .slack import consume_kafka
from .repo import RepoManager
from .events.avro import Serializer
from .events.topics import configure_topics


def create_app():
    """Create the aiohttp.web application.
    """
    config = create_config()
    configure_logging(
        profile=config['api.lsst.codes/profile'],
        log_level=config['api.lsst.codes/logLevel'],
        logger_name=config['api.lsst.codes/loggerName'])

    root_app = web.Application()
    root_app.update(config)
    root_app.add_routes(init_root_routes())
    root_app.cleanup_ctx.append(init_http_session)

    # Create sub-app for the app's public APIs at the correct prefix
    prefix = '/' + root_app['api.lsst.codes/name']
    app = web.Application()
    setup_middleware(app)
    app.add_routes(init_routes())
    app['root'] = root_app  # to make the root app's configs available
    app.cleanup_ctx.append(init_repo_manager)
    app.cleanup_ctx.append(init_serializer)
    app.cleanup_ctx.append(init_topics)
    app.on_startup.append(start_slack_listener)
    app.on_cleanup.append(stop_slack_listener)
    root_app.add_subapp(prefix, app)

    logger = structlog.get_logger(root_app['api.lsst.codes/loggerName'])
    logger.info('Started templatebot')

    return root_app


def configure_logging(profile='development', log_level='info',
                      logger_name='templatebot'):
    """Configure logging and structlog.
    """
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger(logger_name)
    logger.addHandler(stream_handler)
    logger.setLevel(log_level.upper())

    if profile == 'production':
        # JSON-formatted logging
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Key-value formatted logging
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


async def init_http_session(app):
    """Create an aiohttp.ClientSession and make it available as a
    ``'api.lsst.codes/httpSession'`` key on the application.

    Notes
    -----
    Use this function as a `cleanup context`_:

    .. code-block:: python

       python.cleanup_ctx.append(init_http_session)

    The session is automatically closed on shut down.

    Access the session:

    .. code-block:: python

        session = app['api.lsst.codes/httpSession']

    .. cleanup context:
       https://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application.cleanup_ctx
    """
    # Startup phase
    session = ClientSession()
    app['api.lsst.codes/httpSession'] = session
    yield

    # Cleanup phase
    await app['api.lsst.codes/httpSession'].close()


async def start_slack_listener(app):
    """Start the Kafka consumer as a background task (``on_startup`` signal
    handler).
    """
    app['kafka_consumer_task'] = app.loop.create_task(consume_kafka(app))


async def stop_slack_listener(app):
    """Stop the Kafka consumer (``on_cleanup`` signal handler).
    """
    app['kafka_consumer_task'].cancel()
    await app['kafka_consumer_task']


async def init_repo_manager(app):
    """Create and cleanup the RepoManager.
    """
    manager = RepoManager(
        url=app['root']['templatebot/repoUrl'],
        cache_dir=Path('.templatebot_repos'),
        logger=structlog.get_logger(app['root']['api.lsst.codes/loggerName']))
    manager.clone(gitref=app['root']['templatebot/repoRef'])
    app['templatebot/repo'] = manager

    yield

    app['templatebot/repo'].delete_all()


async def init_serializer(app):
    """Init the Avro serializer for SQuaRE Events.
    """
    # Start up phase
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])
    logger.info('Setting up Avro serializers')

    registry = RegistryApi(
        session=app['root']['api.lsst.codes/httpSession'],
        url=app['root']['templatebot/registryUrl'])

    serializer = await Serializer.setup(registry=registry, app=app)
    app['templatebot/eventSerializer'] = serializer
    logger.info('Finished setting up Avro serializer for Slack events')

    yield


async def init_topics(app):
    """Initialize Kafka topics for SQuaRE Events.
    """
    # Start up phase
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])
    logger.info('Setting up templatebot Kafka topics')

    configure_topics(app)

    yield
