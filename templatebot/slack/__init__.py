"""Listen for Slack events from Kafka."""

from .router import consume_kafka

__all__ = ["consume_kafka"]
