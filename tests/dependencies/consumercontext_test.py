"""Tests for the consumer context dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from aiokafka import ConsumerRecord
from faststream.kafka.message import FakeConsumer, KafkaMessage

from templatebot.dependencies.consumercontext import (
    ConsumerContext,
    ConsumerContextDependency,
    MessageContextMiddleware,
)
from templatebot.handlers.kafka import kafka_broker


def make_record(*, topic: str, partition: int, offset: int) -> ConsumerRecord:
    return ConsumerRecord(
        topic=topic,
        partition=partition,
        offset=offset,
        timestamp=0,
        timestamp_type=0,
        key=None,
        value=b"{}",
        checksum=None,
        serialized_key_size=-1,
        serialized_value_size=2,
        headers=[],
    )


@pytest_asyncio.fixture
async def dependency() -> AsyncIterator[ConsumerContextDependency]:
    dependency = ConsumerContextDependency()
    await dependency.initialize()
    try:
        yield dependency
    finally:
        await dependency.aclose()


@pytest.mark.asyncio
async def test_middleware_exposes_the_message_while_it_is_handled(
    dependency: ConsumerContextDependency,
) -> None:
    """The dependency sees the message the middleware is wrapping.

    This is the seam that replaced ``faststream_fastapi.Context("message")``,
    which stopped resolving under faststream 0.7.5.
    """
    record = make_record(topic="topic", partition=3, offset=42)
    message = KafkaMessage(record, b"{}", consumer=FakeConsumer())
    middleware = MessageContextMiddleware(record, context=kafka_broker.context)

    async def handler(msg: Any) -> ConsumerContext:
        assert msg is message
        return await dependency()

    context = await middleware.consume_scope(handler, message)

    assert isinstance(context, ConsumerContext)
    assert context.logger._context["kafka"] == {
        "topic": "topic",
        "offset": 42,
        "partition": 3,
    }


@pytest.mark.asyncio
async def test_batch_uses_the_first_record(
    dependency: ConsumerContextDependency,
) -> None:
    first = make_record(topic="topic", partition=0, offset=7)
    second = make_record(topic="topic", partition=0, offset=8)
    message = KafkaMessage((first, second), b"[]", consumer=FakeConsumer())
    middleware = MessageContextMiddleware(first, context=kafka_broker.context)

    async def handler(msg: Any) -> ConsumerContext:
        return await dependency()

    context = await middleware.consume_scope(handler, message)

    assert context.logger._context["kafka"]["offset"] == 7


@pytest.mark.asyncio
async def test_message_is_cleared_after_handling(
    dependency: ConsumerContextDependency,
) -> None:
    record = make_record(topic="topic", partition=0, offset=1)
    message = KafkaMessage(record, b"{}", consumer=FakeConsumer())
    middleware = MessageContextMiddleware(record, context=kafka_broker.context)

    async def handler(msg: Any) -> None:
        return None

    await middleware.consume_scope(handler, message)

    with pytest.raises(RuntimeError, match="MessageContextMiddleware"):
        await dependency()


@pytest.mark.asyncio
async def test_message_is_cleared_when_the_handler_fails(
    dependency: ConsumerContextDependency,
) -> None:
    record = make_record(topic="topic", partition=0, offset=1)
    message = KafkaMessage(record, b"{}", consumer=FakeConsumer())
    middleware = MessageContextMiddleware(record, context=kafka_broker.context)

    async def handler(msg: Any) -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await middleware.consume_scope(handler, message)

    with pytest.raises(RuntimeError, match="MessageContextMiddleware"):
        await dependency()
