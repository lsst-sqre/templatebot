"""Route incoming Slack messages from SQuaRE Events to handlers."""

import re

import structlog

from .handlers import (
    handle_file_creation,
    handle_file_dialog_submission,
    handle_file_select_action,
    handle_generic_help,
    handle_project_creation,
    handle_project_dialog_submission,
    handle_project_select_action,
)

MENTION_PATTERN = re.compile(r"<(@[a-zA-Z0-9]+|!subteam\^[a-zA-Z0-9]+)>")


async def route_event(*, event, schema_id, topic, partition, offset, app):
    """Route an incoming event, from Kafka, to a handler."""
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])
    logger = logger.bind(
        schema_id=schema_id, topic=topic, partition=partition, offset=offset
    )

    if "event" in event:
        if event["event"]["type"] in ("message", "app_mention"):
            if (
                "subtype" in event["event"]
                and event["event"]["subtype"] == "bot_message"
            ):
                # always ignore bot messages
                return

            text = normalize_text(event["event"]["text"])

            if match_help_request(text):
                await handle_generic_help(event=event, app=app, logger=logger)
            elif "create project" in text:
                await handle_project_creation(
                    event=event, app=app, logger=logger
                )
            elif "create file" in text:
                await handle_file_creation(event=event, app=app, logger=logger)

    elif "type" in event and event["type"] == "block_actions":
        # Handle a button press.
        for action in event["actions"]:
            if action["action_id"] == "templatebot_file_select":
                logger.info(
                    "Got a templatebot_file_select",
                    value=action["selected_option"]["value"],
                )
                await handle_file_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app,
                )
            elif action["action_id"] == "templatebot_project_select":
                logger.info(
                    "Got a templatebot_project_select",
                    value=action["selected_option"]["value"],
                )
                await handle_project_select_action(
                    event_data=event,
                    action_data=action,
                    logger=logger,
                    app=app,
                )

    elif "type" in event and event["type"] == "dialog_submission":
        if event["callback_id"].startswith("templatebot_file_dialog_"):
            logger.info(
                "Got a templatebot_file_dialog submission", event_data=event
            )
            await handle_file_dialog_submission(
                event_data=event, logger=logger, app=app
            )
        elif event["callback_id"].startswith("templatebot_project_dialog"):
            logger.info(
                "Got a templatebot_project_dialog submission", event_data=event
            )
            await handle_project_dialog_submission(
                event_data=event, logger=logger, app=app
            )


def normalize_text(input_text):
    """Normalize text from Slack to improve matching.

    - Strips extraneous whitespace.
    - Makes all text lowercase.
    """
    return " ".join(input_text.lower().split())


def match_help_request(original_text):
    # Strip out mentions
    text = MENTION_PATTERN.sub("", original_text)

    # renormalize whitepsace
    text = normalize_text(text)

    # determine if "help" is the only word
    if text in ("help", "help!", "help?"):
        return True
    else:
        return False
