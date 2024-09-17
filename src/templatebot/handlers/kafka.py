"""Kafka router and consumers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from faststream.kafka.fastapi import KafkaRouter
from faststream.security import BaseSecurity
from rubin.squarebot.models.kafka import SquarebotSlackMessageValue
from structlog import get_logger

from ..config import config
from ..dependencies.consumercontext import (
    ConsumerContext,
    consumer_context_dependency,
)

__all__ = ["kafka_router", "handle_slack_message"]


kafka_security = BaseSecurity(ssl_context=config.kafka.ssl_context)
kafka_router = KafkaRouter(
    config.kafka.bootstrap_servers,
    security=kafka_security,
    logger=get_logger(__name__),
)


@kafka_router.subscriber(
    config.message_channels_topic,
    config.message_groups_topic,
    config.message_im_topic,
    config.message_mpim_topic,
    group_id=config.consumer_group_id,
)
async def handle_slack_message(
    message: SquarebotSlackMessageValue,
    context: Annotated[ConsumerContext, Depends(consumer_context_dependency)],
) -> None:
    """Handle a Slack message."""
    logger = context.logger
    factory = context.factory

    logger.debug(
        "Slack message text",
        text=message.text,
    )

    message_service = factory.create_slack_message_service()
    await message_service.handle_message(message)
