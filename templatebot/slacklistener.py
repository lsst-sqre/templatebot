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

            try:
                await route_event(
                    event=message_info['message'],
                    app=app,
                    schema_id=message_info['id'],
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)
            except Exception as e:
                logger.error(
                    'Failed to handle message',
                    error=str(e),
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
        if event['event']['type'] == 'message':
            if 'subtype' in event['event'] \
                    and event['event']['subtype'] == 'bot_message':
                # always ignore bot messages
                return

            text = normalize_text(event['event']['text'])

            if 'create project' in text:
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


def normalize_text(input_text):
    """Normalize text from Slack to improve matching.

    - Strips extraneous whitespace.
    - Makes all text lowercase.
    """
    return ' '.join(input_text.lower().split())


async def handle_project_creation(*, event, app, logger):
    """Handle an initial event from a user asking to make a new project
    (typically a GitHub repository).

    Parameters
    ----------
    event : `dict`
        The body of the Slack event.
    app : `aiohttp.web.Application`
        The application instance.
    logger
        A structlog logger, typically with event information already
        bound to it.
    """
    event_channel = event['event']['channel']
    calling_user = event['event']['user']

    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_channel,
        # Since there are `blocks`, this is a fallback for notifications
        "text": (
            f"<@{calling_user}>, what type of project do you "
            "want to make?"
        ),
        'blocks': [
            {
                "type": "section",
                "block_id": "templatebot_project_select",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{calling_user}>, what type of project do you "
                        "want to make?"
                    )
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "templatebot_project_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template",
                        "emoji": True
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_package",
                                "emoji": True
                            },
                            "value": "stack_package"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "nbreport",
                                "emoji": True
                            },
                            "value": "nbreport"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "technote_rst",
                                "emoji": True
                            },
                            "value": "technote_rst"
                        }
                    ]
                }
            }
        ]
    }
    url = 'https://slack.com/api/chat.postMessage'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.postMessage',
            contents=response_json)


async def handle_file_creation(*, event, app, logger):
    """Handle an initial event from a user asking to make a new file or
    snippet.

    Parameters
    ----------
    event : `dict`
        The body of the Slack event.
    app : `aiohttp.web.Application`
        The application instance.
    logger
        A structlog logger, typically with event information already
        bound to it.
    """
    event_channel = event['event']['channel']
    calling_user = event['event']['user']

    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_channel,
        # Since there are `blocks`, this is a fallback for notifications
        "text": (
            f"<@{calling_user}>, what type of file or snippet do you "
            "want to make?"
        ),
        'blocks': [
            {
                "type": "section",
                "block_id": "templatebot_file_select",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{calling_user}>, what type of file or snippet do "
                        "you want to make?"
                    )
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "templatebot_file_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template",
                        "emoji": True
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "config_topic",
                                "emoji": True
                            },
                            "value": "config_topic"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "copyright",
                                "emoji": True
                            },
                            "value": "copyright"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "license_gplv3",
                                "emoji": True
                            },
                            "value": "license_gplv3"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_cpp",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_cpp"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_py",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_py"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_txt",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_txt"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "task_topic",
                                "emoji": True
                            },
                            "value": "task_topic"
                        },
                    ]
                }
            }
        ]
    }
    url = 'https://slack.com/api/chat.postMessage'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.postMessage',
            contents=response_json)


async def handle_file_select_action(*, event_data, action_data, logger, app):
    """Handle the selection from a ``templatebot_file_select`` action ID.
    """
    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }

    text_content = (
        f"<@{event_data['user']['id']}> :raised_hands: "
        "Nice! I'll help you create boilerplate for a "
        f"`{action_data['selected_option']['text']['text']}` snippet."
    )
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_data['container']['channel_id'],
        'text': text_content,
        "ts": event_data['container']['message_ts'],
        "blocks": [
            {
                "type": "section",
                "text": {
                    "text": text_content,
                    "type": "mrkdwn"
                }
            }
        ]
    }

    logger.info(
        'templatebot_file_select chat.update',
        body=body)

    url = 'https://slack.com/api/chat.update'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.info(
            'templatebot_file_select reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.update',
            contents=response_json)
