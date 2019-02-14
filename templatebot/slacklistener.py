"""Listen for Slack events from Kafka.
"""

__all__ = ('consume_kafka',)

import asyncio

import structlog


async def consume_kafka(app):
    """Consume Kafka messages directed to templatebot's functionality.
    """
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])

    try:
        while True:
            logger.info('In consume_kafka task loop')
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info('consume_kafka task got cancelled')
    finally:
        logger.info('consume_kafka task cancelling')
