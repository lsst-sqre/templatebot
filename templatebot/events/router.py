"""Router that listens to Kafka topics related to the templatebot aide
that indicates a GitHub repo is ready to populate.
"""

import asyncio

import structlog
from aiokafka import AIOKafkaConsumer
from kafkit.registry import Deserializer
from kafkit.registry.aiohttp import RegistryApi

from .handlers import handle_project_render

__all__ = ["consume_events"]


async def consume_events(app):
    """Consume events from templatebot-related topics in SQuaRE Events (Kafka).

    Notes
    -----
    Templatebot has *two* Kafka consumers. This is one, and the other is
    in `templatebot.slack`. The Slack consumer only listens to topics from
    Slack (SQuaRE Bot), and is focused on responding to Slack-based workflows.
    This consumer is focused on backend-driven events, such as the
    ``templatebot-render_ready`` topic.
    """
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])

    registry = RegistryApi(
        session=app["root"]["api.lsst.codes/httpSession"],
        url=app["root"]["templatebot/registryUrl"],
    )
    deserializer = Deserializer(registry=registry)

    consumer_settings = {
        "bootstrap_servers": app["root"]["templatebot/brokerUrl"],
        "group_id": app["root"]["templatebot/eventsGroupId"],
        "auto_offset_reset": "latest",
        "ssl_context": app["root"]["templatebot/kafkaSslContext"],
        "security_protocol": app["root"]["templatebot/kafkaProtocol"],
    }
    consumer = AIOKafkaConsumer(
        loop=asyncio.get_event_loop(), **consumer_settings
    )

    try:
        await consumer.start()
        logger.info("Started Kafka consumer for events", **consumer_settings)

        topic_names = [app["root"]["templatebot/renderreadyTopic"]]
        logger.info("Subscribing to Kafka topics", names=topic_names)
        consumer.subscribe(topic_names)

        partitions = consumer.assignment()
        while len(partitions) == 0:
            # Wait for the consumer to get partition assignment
            await asyncio.sleep(1.0)
            partitions = consumer.assignment()
        logger.info(
            "Initial partition assignment for event topics",
            partitions=[str(p) for p in partitions],
        )

        async for message in consumer:
            try:
                message_info = await deserializer.deserialize(
                    message.value, include_schema=True
                )
            except Exception:
                logger.exception(
                    "Failed to deserialize an event message",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
                continue

            event = message_info["message"]
            logger.debug(
                "New event message",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                contents=event,
            )

            try:
                await route_event(
                    app=app,
                    event=message_info["message"],
                    schema_id=message_info["id"],
                    schema=message_info["schema"],
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
            except Exception:
                logger.exception(
                    "Failed to handle event message",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )

    except asyncio.CancelledError:
        logger.info("consume_events task got cancelled")
    finally:
        logger.info("consume_events task cancelling")
        await consumer.stop()


async def route_event(
    *, event, app, schema_id, schema, topic, partition, offset
):
    """Route events from `consume_events` to specific handlers."""
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger = logger.bind(
        topic=topic, partition=partition, offset=offset, schema_id=schema_id
    )

    if topic == app["root"]["templatebot/renderreadyTopic"]:
        await handle_project_render(
            event=event, schema=schema, app=app, logger=logger
        )
