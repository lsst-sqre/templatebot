"""Route incoming Slack messages from SQuaRE Events to handlers.
"""

__all__ = ('consume_kafka',)

import asyncio
import re

from aiokafka import AIOKafkaConsumer
from kafkit.registry.aiohttp import RegistryApi
from kafkit.registry import Deserializer
import structlog

from .handlers import (
    handle_project_creation, handle_file_creation,
    handle_file_select_action, handle_file_dialog_submission,
    handle_project_select_action, handle_project_dialog_submission,
    handle_generic_help
)


MENTION_PATTERN = re.compile(r'<(@[a-zA-Z0-9]+|!subteam\^[a-zA-Z0-9]+)>')


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
            logger.info(
                'Got Kafka message from sqrbot',
                topic=message.topic,
                partition=message.partition,
                offset=message.offset)
            try:
                message_info = await deserializer.deserialize(message.value)
            except Exception:
                logger.exception(
                    'Failed to deserialize a message',
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)
                continue

            event = message_info['message']
            logger.debug(
                'New message',
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                contents=event)

            try:
                await route_event(
                    event=message_info['message'],
                    app=app,
                    schema_id=message_info['id'],
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)
            except Exception:
                logger.exception(
                    'Failed to handle message',
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)

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
    events = set(['app_mention', 'message.im', 'interaction'])

    topic_names = []
    for event in events:
        if suffix:
            topic_name = f'sqrbot-{event}-{suffix}'
        else:
            topic_name = f'sqrbot-{event}'
        topic_names.append(topic_name)

    return topic_names


async def route_event(*, event, schema_id, topic, partition, offset, app):
    """Route an incoming event, from Kafka, to a handler.
    """
    logger = structlog.get_logger(app['root']['api.lsst.codes/loggerName'])
    logger = logger.bind(schema_id=schema_id, topic=topic, partition=partition,
                         offset=offset)

    if 'event' in event:
        if event['event']['type'] in ('message', 'app_mention'):
            if 'subtype' in event['event'] \
                    and event['event']['subtype'] == 'bot_message':
                # always ignore bot messages
                return

            text = normalize_text(event['event']['text'])

            if match_help_request(text):
                await handle_generic_help(
                    event=event, app=app, logger=logger)
            elif 'create project' in text:
                await handle_project_creation(
                    event=event, app=app, logger=logger)
            elif 'create file' in text:
                await handle_file_creation(event=event, app=app, logger=logger)

    elif 'type' in event and event['type'] == 'block_actions':
        # Handle a button press.
        for action in event['actions']:
            if action['action_id'] == 'templatebot_file_select':
                logger.info(
                    'Got a templatebot_file_select',
                    value=action['selected_option']['value'])
                await handle_file_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app)
            elif action['action_id'] == 'templatebot_project_select':
                logger.info(
                    'Got a templatebot_project_select',
                    value=action['selected_option']['value'])
                await handle_project_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app)

    elif 'type' in event and event['type'] == 'dialog_submission':
        if event['callback_id'].startswith('templatebot_file_dialog_'):
            logger.info(
                'Got a templatebot_file_dialog submission',
                event_data=event)
            await handle_file_dialog_submission(
                event_data=event,
                logger=logger,
                app=app
            )
        elif event['callback_id'].startswith('templatebot_project_dialog'):
            logger.info(
                'Got a templatebot_project_dialog submission',
                event_data=event)
            await handle_project_dialog_submission(
                event_data=event,
                logger=logger,
                app=app
            )


def normalize_text(input_text):
    """Normalize text from Slack to improve matching.

    - Strips extraneous whitespace.
    - Makes all text lowercase.
    """
    return ' '.join(input_text.lower().split())


def match_help_request(original_text):
    # Strip out mentions
    text = MENTION_PATTERN.sub('', original_text)

    # renormalize whitepsace
    text = normalize_text(text)

    # determine if "help" is the only word
    if text in ('help', 'help!', 'help?'):
        return True
    else:
        return False
