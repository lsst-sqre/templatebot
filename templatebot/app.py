"""Application factory for the aiohttp.web-based app."""

import asyncio
import logging
import os
import ssl
import sys
from pathlib import Path

import cachetools
import structlog
from aiohttp import ClientSession, web
from aiokafka import AIOKafkaProducer
from gidgethub.aiohttp import GitHubAPI
from kafkit.registry.aiohttp import RegistryApi

from .config import create_config
from .events.avro import Serializer
from .events.router import consume_events
from .events.topics import configure_topics
from .middleware import setup_middleware
from .repo import RepoManager
from .routes import init_root_routes, init_routes
from .slack import consume_kafka

__all__ = ["create_app"]


def create_app():
    """Create the aiohttp.web application."""
    config = create_config()
    configure_logging(
        profile=config["api.lsst.codes/profile"],
        log_level=config["api.lsst.codes/logLevel"],
        logger_name=config["api.lsst.codes/loggerName"],
    )

    root_app = web.Application()
    root_app.update(config)
    root_app.add_routes(init_root_routes())
    root_app.cleanup_ctx.append(init_http_session)
    root_app.cleanup_ctx.append(init_gidgethub_session)

    # Create sub-app for the app's public APIs at the correct prefix
    prefix = "/" + root_app["api.lsst.codes/name"]
    app = web.Application()
    setup_middleware(app)
    app.add_routes(init_routes())
    app["root"] = root_app  # to make the root app's configs available
    app.cleanup_ctx.append(init_repo_manager)
    app.cleanup_ctx.append(init_serializer)
    app.cleanup_ctx.append(configure_kafka_ssl)
    if root_app["templatebot/enableTopicConfig"]:
        app.cleanup_ctx.append(init_topics)
    app.cleanup_ctx.append(init_producer)
    if root_app["templatebot/enableSlackConsumer"]:
        app.on_startup.append(start_slack_listener)
        app.on_cleanup.append(stop_slack_listener)
    if root_app["templatebot/enableEventsConsumer"]:
        app.on_startup.append(start_events_listener)
        app.on_cleanup.append(stop_events_listener)
    root_app.add_subapp(prefix, app)

    logger = structlog.get_logger(root_app["api.lsst.codes/loggerName"])
    logger.info("Started templatebot")

    return root_app


def configure_logging(
    profile="development", log_level="info", logger_name="templatebot"
):
    """Configure logging and structlog."""
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger(logger_name)
    logger.addHandler(stream_handler)
    logger.setLevel(log_level.upper())

    if profile == "production":
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
            structlog.dev.ConsoleRenderer(),
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
    app["api.lsst.codes/httpSession"] = session
    yield

    # Cleanup phase
    await app["api.lsst.codes/httpSession"].close()


async def init_gidgethub_session(app):
    """Create a Gidgethub client session to access the GitHub api.

    Notes
    -----
    Use this function as a cleanup content.

    Access the client as ``app['templatebot/gidgethub']``.
    """
    session = app["api.lsst.codes/httpSession"]
    token = app["templatebot/githubToken"]
    username = app["templatebot/githubUsername"]
    cache = cachetools.LRUCache(maxsize=500)
    gh = GitHubAPI(session, username, oauth_token=token, cache=cache)
    app["templatebot/gidgethub"] = gh

    yield

    # No cleanup to do


async def configure_kafka_ssl(app):
    """Configure an SSL context for the Kafka client (if appropriate).

    Notes
    -----
    Use this function as a `cleanup context`_:

    .. code-block:: python

       app.cleanup_ctx.append(init_http_session)
    """
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])

    ssl_context_key = "templatebot/kafkaSslContext"

    if app["root"]["templatebot/kafkaProtocol"] != "SSL":
        app["root"][ssl_context_key] = None
        return

    cluster_ca_cert_path = app["root"]["templatebot/clusterCaPath"]
    client_ca_cert_path = app["root"]["templatebot/clientCaPath"]
    client_cert_path = app["root"]["templatebot/clientCertPath"]
    client_key_path = app["root"]["templatebot/clientKeyPath"]

    if cluster_ca_cert_path is None:
        raise RuntimeError("Kafka protocol is SSL but cluster CA is not set")
    if client_cert_path is None:
        raise RuntimeError("Kafka protocol is SSL but client cert is not set")
    if client_key_path is None:
        raise RuntimeError("Kafka protocol is SSL but client key is not set")

    if client_ca_cert_path is not None:
        logger.info("Contatenating Kafka client CA and certificate files.")
        # Need to contatenate the client cert and CA certificates. This is
        # typical for Strimzi-based Kafka clusters.
        client_ca = Path(client_ca_cert_path).read_text()
        client_cert = Path(client_cert_path).read_text()
        new_client_cert = "\n".join([client_cert, client_ca])
        new_client_cert_path = Path(os.getenv("APPDIR", ".")) / "client.crt"
        new_client_cert_path.write_text(new_client_cert)
        client_cert_path = str(new_client_cert_path)

    # Create a SSL context on the basis that we're the client authenticating
    # the server (the Kafka broker).
    ssl_context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH, cafile=cluster_ca_cert_path
    )
    # Add the certificates that the Kafka broker uses to authenticate us.
    ssl_context.load_cert_chain(
        certfile=client_cert_path, keyfile=client_key_path
    )
    app["root"][ssl_context_key] = ssl_context

    logger.info("Created Kafka SSL context")

    yield


async def start_slack_listener(app):
    """Start the Kafka consumer as a background task (``on_startup`` signal
    handler).
    """
    app["kafka_consumer_task"] = app.loop.create_task(consume_kafka(app))


async def stop_slack_listener(app):
    """Stop the Kafka consumer (``on_cleanup`` signal handler)."""
    app["kafka_consumer_task"].cancel()
    await app["kafka_consumer_task"]


async def init_repo_manager(app):
    """Create and cleanup the RepoManager."""
    manager = RepoManager(
        url=app["root"]["templatebot/repoUrl"],
        cache_dir=app["root"]["templatebot/repoCachePath"],
        logger=structlog.get_logger(app["root"]["api.lsst.codes/loggerName"]),
    )
    manager.clone(gitref=app["root"]["templatebot/repoRef"])
    app["templatebot/repo"] = manager

    yield

    app["templatebot/repo"].delete_all()


async def init_serializer(app):
    """Init the Avro serializer for SQuaRE Events."""
    # Start up phase
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger.info("Setting up Avro serializers")

    registry = RegistryApi(
        session=app["root"]["api.lsst.codes/httpSession"],
        url=app["root"]["templatebot/registryUrl"],
    )

    serializer = await Serializer.setup(registry=registry, app=app)
    app["templatebot/eventSerializer"] = serializer
    logger.info("Finished setting up Avro serializer for Slack events")

    yield


async def init_topics(app):
    """Initialize Kafka topics for SQuaRE Events."""
    # Start up phase
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger.info("Setting up templatebot Kafka topics")

    configure_topics(app)

    yield


async def start_events_listener(app):
    """Start the Kafka consumer for templatebot events as a background task
    (``on_startup`` signal handler).
    """
    app["templatebot/events_consumer_task"] = app.loop.create_task(
        consume_events(app)
    )


async def stop_events_listener(app):
    """Stop the Kafka consumer for templatebot events (``on_cleanup`` signal
    handler).
    """
    app["templatebot/events_consumer_task"].cancel()
    await app["templatebot/events_consumer_task"]


async def init_producer(app):
    """Initialize and cleanup the aiokafka Producer instance

    Notes
    -----
    Use this function as a cleanup context, see
    https://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application.cleanup_ctx

    To access the producer:

    .. code-block:: python

       producer = app['templatebot/producer']
    """
    # Startup phase
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger.info("Starting Kafka producer")
    loop = asyncio.get_running_loop()
    producer = AIOKafkaProducer(
        loop=loop,
        bootstrap_servers=app["root"]["templatebot/brokerUrl"],
        ssl_context=app["root"]["templatebot/kafkaSslContext"],
        security_protocol=app["root"]["templatebot/kafkaProtocol"],
    )
    await producer.start()
    app["templatebot/producer"] = producer
    logger.info("Finished starting Kafka producer")

    yield

    # cleanup phase
    logger.info("Shutting down Kafka producer")
    await producer.stop()
