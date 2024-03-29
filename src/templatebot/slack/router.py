"""Route incoming Slack messages from SQuaRE Events to handlers."""

import asyncio
import re

import structlog
from aiokafka import AIOKafkaConsumer
from kafkit.registry import Deserializer
from kafkit.registry.aiohttp import RegistryApi

from .handlers import (
    handle_file_creation,
    handle_file_dialog_submission,
    handle_file_select_action,
    handle_generic_help,
    handle_project_creation,
    handle_project_dialog_submission,
    handle_project_select_action,
)

__all__ = ["consume_kafka"]

MENTION_PATTERN = re.compile(r"<(@[a-zA-Z0-9]+|!subteam\^[a-zA-Z0-9]+)>")


async def consume_kafka(app):
    """Consume Kafka messages directed to templatebot's functionality."""
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])

    registry = RegistryApi(
        session=app["root"]["api.lsst.codes/httpSession"],
        url=app["root"]["templatebot/registryUrl"],
    )
    deserializer = Deserializer(registry=registry)

    consumer_settings = {
        "bootstrap_servers": app["root"]["templatebot/brokerUrl"],
        "group_id": app["root"]["templatebot/slackGroupId"],
        "auto_offset_reset": "latest",
        "ssl_context": app["root"]["templatebot/kafkaSslContext"],
        "security_protocol": app["root"]["templatebot/kafkaProtocol"],
    }
    consumer = AIOKafkaConsumer(
        loop=asyncio.get_event_loop(), **consumer_settings
    )

    try:
        await consumer.start()
        logger.info("Started Kafka consumer", **consumer_settings)

        topic_names = [
            app["root"]["templatebot/appMentionTopic"],
            app["root"]["templatebot/messageImTopic"],
            app["root"]["templatebot/interactionTopic"],
        ]
        logger.info("Subscribing to Kafka topics", names=topic_names)
        consumer.subscribe(topic_names)

        logger.info("Finished subscribing ot Kafka topics", names=topic_names)

        partitions = consumer.assignment()
        logger.info("Waiting on partition assignment", names=topic_names)
        while len(partitions) == 0:
            # Wait for the consumer to get partition assignment
            await asyncio.sleep(1.0)
            partitions = consumer.assignment()
        logger.info(
            "Initial partition assignment",
            partitions=[str(p) for p in partitions],
        )

        async for message in consumer:
            logger.info(
                "Got Kafka message from sqrbot",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
            )
            try:
                message_info = await deserializer.deserialize(message.value)
            except Exception:
                logger.exception(
                    "Failed to deserialize a message",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
                continue

            event = message_info["message"]
            logger.debug(
                "New message",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                contents=event,
            )

            try:
                await route_event(
                    event=message_info["message"],
                    app=app,
                    schema_id=message_info["id"],
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
            except Exception:
                logger.exception(
                    "Failed to handle message",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )

    except asyncio.CancelledError:
        logger.info("consume_kafka task got cancelled")
    finally:
        logger.info("consume_kafka task cancelling")
        await consumer.stop()


async def route_event(*, event, schema_id, topic, partition, offset, app):
    """Route an incoming event, from Kafka, to a handler."""
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger = logger.bind(
        schema_id=schema_id, topic=topic, partition=partition, offset=offset
    )

    if "event" in event:
        if event["event"]["type"] in ("message", "app_mention"):
            if (
                "subtype" in event["event"]
                and event["event"]["subtype"] == "bot_message"
            ):
                # always ignore bot messages
                return

            text = normalize_text(event["event"]["text"])

            if match_help_request(text):
                await handle_generic_help(event=event, app=app, logger=logger)
            elif "create project" in text:
                await handle_project_creation(
                    event=event, app=app, logger=logger
                )
            elif "create file" in text:
                await handle_file_creation(event=event, app=app, logger=logger)

    elif "type" in event and event["type"] == "block_actions":
        # Handle a button press.
        for action in event["actions"]:
            if action["action_id"] == "templatebot_file_select":
                logger.info(
                    "Got a templatebot_file_select",
                    value=action["selected_option"]["value"],
                )
                await handle_file_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app,
                )
            elif action["action_id"] == "templatebot_project_select":
                logger.info(
                    "Got a templatebot_project_select",
                    value=action["selected_option"]["value"],
                )
                await handle_project_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app,
                )

    elif "type" in event and event["type"] == "dialog_submission":
        if event["callback_id"].startswith("templatebot_file_dialog_"):
            logger.info(
                "Got a templatebot_file_dialog submission", event_data=event
            )
            await handle_file_dialog_submission(
                event_data=event, logger=logger, app=app
            )
        elif event["callback_id"].startswith("templatebot_project_dialog"):
            logger.info(
                "Got a templatebot_project_dialog submission", event_data=event
            )
            await handle_project_dialog_submission(
                event_data=event, logger=logger, app=app
            )


def normalize_text(input_text):
    """Normalize text from Slack to improve matching.

    - Strips extraneous whitespace.
    - Makes all text lowercase.
    """
    return " ".join(input_text.lower().split())


def match_help_request(original_text):
    # Strip out mentions
    text = MENTION_PATTERN.sub("", original_text)

    # renormalize whitepsace
    text = normalize_text(text)

    # determine if "help" is the only word
    if text in ("help", "help!", "help?"):
        return True
    else:
        return False
