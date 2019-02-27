"""Listen for Slack events from Kafka.
"""

__all__ = ('consume_kafka',)

from .router import consume_kafka
