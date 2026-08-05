"""Kafka router and consumers."""

from typing import Annotated

from fastapi import Depends
from faststream.kafka import KafkaBroker
from faststream.security import BaseSecurity
from rubin.squarebot.models.kafka import (
    SquarebotSlackAppMentionValue,
    SquarebotSlackBlockActionsValue,
    SquarebotSlackMessageValue,
    SquarebotSlackViewSubmissionValue,
)
from structlog import get_logger

from ..config import config
from ..dependencies.consumercontext import (
    ConsumerContext,
    consumer_context_dependency,
)

__all__ = ["handle_slack_message", "kafka_broker"]


# The connection config here is hand-rolled (not safir.kafka.
# KafkaConnectionSettings) because it supports concatenating a client
# certificate with a client CA certificate for Strimzi installations
# (cert_temp_dir/client_ca_path), which safir.kafka.KafkaConnectionSettings
# does not. Normalizing to safir.kafka would drop that capability and would
# reject the KAFKA_CERT_TEMP_DIR/KAFKA_CLIENT_CA_PATH/KAFKA_CLIENT_KEY_PASSWORD
# env vars Phalanx may set (safir's settings model uses extra="forbid"), so
# it is deliberately left as-is here.
kafka_security = BaseSecurity(ssl_context=config.kafka.ssl_context)
# The broker is wrapped by FastStreamAPI in main.py, which starts it before
# entering the application lifespan and stops it after exit.
kafka_broker = KafkaBroker(
    config.kafka.bootstrap_servers,
    security=kafka_security,
    logger=get_logger(__name__),
)


@kafka_broker.subscriber(
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


@kafka_broker.subscriber(
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


@kafka_broker.subscriber(
    config.block_actions_topic,
    group_id=f"{config.consumer_group_id}-block-actions",
)
async def handle_slack_block_actions(
    payload: SquarebotSlackBlockActionsValue,
    context: Annotated[ConsumerContext, Depends(consumer_context_dependency)],
) -> None:
    """Handle a Slack block_actions interaction."""
    logger = context.logger
    factory = context.factory

    logger.debug(
        "Got Slack block_actions",
        actions=payload.actions[0].model_dump(mode="json"),
    )
    block_actions_service = factory.create_slack_block_actions_service()
    await block_actions_service.handle_block_actions(payload)


@kafka_broker.subscriber(
    config.view_submission_topic,
    group_id=f"{config.consumer_group_id}-view-submission",
)
async def handle_slack_view_submission(
    payload: SquarebotSlackViewSubmissionValue,
    context: Annotated[ConsumerContext, Depends(consumer_context_dependency)],
) -> None:
    """Handle a Slack view submission interaction."""
    logger = context.logger
    factory = context.factory

    logger.debug(
        "Handling view submission",
        payload=payload.model_dump(mode="json"),
    )
    view_service = factory.create_slack_view_service()
    await view_service.handle_view_submission(payload)
