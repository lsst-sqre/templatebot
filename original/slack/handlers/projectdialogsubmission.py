"""Handle a project_dialog_submission event after the user has filled out
a dialog with template configuration.
"""

import datetime
import json

from templatebot.slack.chat import post_message, update_message
from templatebot.slack.dialog import post_process_dialog_submission

__all__ = ["handle_project_dialog_submission"]


async def handle_project_dialog_submission(*, event_data, logger, app):
    """Handle the dialog_submission interaction from a
    ``templatebot_project_dialog``.
    """
    channel_id = event_data["channel"]["id"]
    user_id = event_data["user"]["id"]
    state = json.loads(event_data["state"])

    template_name = state["template_name"]
    repo = app["templatebot/repo"].get_repo(
        gitref=app["root"]["templatebot/repoRef"]
    )
    template = repo[template_name]

    template_variables = post_process_dialog_submission(
        submission_data=event_data["submission"], template=template
    )
    logger.info(
        "project dialog submission",
        variables=template_variables,
        template=template.name,
        user_id=user_id,
        channel_id=channel_id,
    )

    # Send a notification message to the user on Slack
    body = {
        "token": app["root"]["templatebot/slackToken"],
        "channel": channel_id,
        # Since there are `blocks`, this is a fallback for notifications
        "text": (
            f"<@{user_id}>, got it! I'll start working on your "
            f"{template.config['name']} repository right away. I'll keep you "
            "updated!"
        ),
    }
    if (
        "trigger_message_ts" in state
        and state["trigger_message_ts"] is not None
    ):
        # Post the status update as a replacement of the original trigger
        # message (the selection menu).
        body["ts"] = state["trigger_message_ts"]
        body["blocks"] = [
            {
                "type": "section",
                "text": {"text": body["text"], "type": "mrkdwn"},
            }
        ]
        response_json = await update_message(body=body, app=app, logger=logger)
        slack_thread_ts = response_json["ts"]
    else:
        # Post a new message
        response_json = await post_message(body=body, app=app, logger=logger)
        slack_thread_ts = response_json["message"]["ts"]

    # Send a templatebot-prerender event
    prerender_payload = {
        "template_name": template.name,
        "variables": template_variables,
        "template_repo": app["root"]["templatebot/repoUrl"],
        "template_repo_ref": app["root"]["templatebot/repoRef"],
        "retry_count": 0,
        "initial_timestamp": datetime.datetime.now(datetime.UTC),
        "slack_username": user_id,
        "slack_channel": channel_id,
        "slack_thread_ts": slack_thread_ts,
    }
    serializer = app["templatebot/eventSerializer"]
    prerender_data = await serializer.serialize(
        "templatebot.prerender_v1", prerender_payload
    )
    producer = app["templatebot/producer"]
    topic_name = app["root"]["templatebot/prerenderTopic"]
    await producer.send_and_wait(topic_name, prerender_data)
    logger.info(
        "Sent prerender event",
        prerender_topic=topic_name,
        payload=prerender_payload,
    )
