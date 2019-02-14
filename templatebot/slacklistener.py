"""Listen for Slack events from Kafka.
"""

__all__ = ('consume_kafka',)

import asyncio

from aiokafka import AIOKafkaConsumer
from kafkit.registry.aiohttp import RegistryApi
from kafkit.registry import Deserializer
import structlog


async def consume_kafka(app):
    """Consume Kafka messages directed to templatebot's functionality.
    """
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])

    registry = RegistryApi(
        session=app['root']['api.lsst.codes/httpSession'],
        url=app['root']['templatebot/registryUrl'])
    deserializer = Deserializer(registry=registry)

    if app['root']['templatebot/topicsVersion']:
        group_id = '_'.join((app["root"]["api.lsst.codes/name"],
                             app['root']['templatebot/topicsVersion']))
    else:
        group_id = app['root']['api.lsst.codes/name']
    consumer_settings = {
        'bootstrap_servers': app['root']['templatebot/brokerUrl'],
        'group_id': group_id,
        'auto_offset_reset': 'latest'
    }
    consumer = AIOKafkaConsumer(
        loop=asyncio.get_event_loop(),
        **consumer_settings)

    try:
        await consumer.start()
        logger.info('Started Kafka consumer', **consumer_settings)

        topic_names = get_topic_names(
            suffix=app['root']['templatebot/topicsVersion'])
        logger.info('Subscribing to Kafka topics', names=topic_names)
        consumer.subscribe(topic_names)

        partitions = consumer.assignment()
        while len(partitions) == 0:
            # Wait for the consumer to get partition assignment
            await asyncio.sleep(1.)
            partitions = consumer.assignment()
        logger.info(
            'Initial partition assignment',
            partitions=[str(p) for p in partitions])

        async for message in consumer:
            try:
                message_info = await deserializer.deserialize(message.value)
            except Exception as e:
                logger.error(
                    'Failed to deserialize a message',
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                    error=str(e))
                continue

            event = message_info['message']
            logger.debug(
                'New message',
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                contents=event)

    except asyncio.CancelledError:
        logger.info('consume_kafka task got cancelled')
    finally:
        logger.info('consume_kafka task cancelling')
        await consumer.stop()


def get_topic_names(suffix=''):
    """Get the list of Kafka topics that should be subscribed to.
    """
    # NOTE: a lot of this is very similar to sqrbot.topics.py; this might be
    # good to put in a common SQuaRE Events package.

    # Only want to subscribe to app_mention and message.im because these
    # are the events that can trigger templatebot actions. We don't care
    # about general messages (messages.channels, for example).
    events = set(['app_mention', 'message.im'])

    topic_names = []
    for event in events:
        if suffix:
            topic_name = f'sqrbot-{event}-{suffix}'
        else:
            topic_name = f'sqrbot-{event}'
        topic_names.append(topic_name)

    return topic_names
