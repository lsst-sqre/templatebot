"""Kafka router and consumers."""

from typing import Annotated

from fastapi import Depends
from faststream.kafka.fastapi import KafkaRouter
from faststream.security import BaseSecurity
from rubin.squarebot.models.kafka import (
    SquarebotSlackAppMentionValue,
    SquarebotSlackBlockActionsValue,
    SquarebotSlackMessageValue,
)
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
    config.message_im_topic,
    group_id=f"{config.consumer_group_id}-im",
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
    await message_service.handle_im_message(message)


@kafka_router.subscriber(
    config.app_mention_topic,
    group_id=f"{config.consumer_group_id}-app-mention",
)
async def handle_slack_app_mention(
    message: SquarebotSlackAppMentionValue,
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
    await message_service.handle_app_mention(message)


@kafka_router.subscriber(
    config.block_actions_topic,
    group_id=f"{config.consumer_group_id}-block-actions",
)
async def handle_slack_block_actions(
    payload: SquarebotSlackBlockActionsValue,
    context: Annotated[ConsumerContext, Depends(consumer_context_dependency)],
) -> None:
    """Handle a Slack block_actions interaction."""
    logger = context.logger

    logger.debug(
        "Got Slack block_actions",
        actions=payload.actions[0].model_dump(mode="json"),
    )
