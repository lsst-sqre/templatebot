"""Slack handler for when a user selects project template from a menu.
"""

__all__ = ('handle_project_select_action',)

from templatebot.slack.dialog import open_template_dialog
from templatebot.slack.chatupdate import update_message


async def handle_project_select_action(*, event_data, action_data, logger,
                                       app):
    """Handle the selection from a ``templatebot_project_select`` action ID.

    The key steps are:

    1. Use the ``chat.update`` method to replace the original message
       containing a selection menu with a confirmation message. This prevents
       someone from interacting with the menu again.
    2. Open a Slack dialog to let the user fill in template variables based
       on the ``cookiecutter.json`` file.
    """
    await _confirm_selection(event_data=event_data, action_data=action_data,
                             logger=logger, app=app)

    selected_template = action_data['selected_option']['value']
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[selected_template]
    await open_template_dialog(template=template, event_data=event_data,
                               callback_id_root="templatebot_project_dialog",
                               logger=logger, app=app)


async def _confirm_selection(*, event_data, action_data, logger, app):
    """Confirm the menu selection by replacing the menu with a static message.
    """
    text_content = (
        f"<@{event_data['user']['id']}> :raised_hands: "
        "Nice! I'll help you create boilerplate for a "
        f"`{action_data['selected_option']['text']['text']}` repo."
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
    await update_message(body=body, logger=logger, app=app)
