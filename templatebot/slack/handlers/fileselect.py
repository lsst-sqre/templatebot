"""Slack handler for when a user selects a file template from a menu.
"""

__all__ = ('handle_file_select_action',)

from templatebot.slack.dialog import open_template_dialog
from templatebot.slack.chat import update_message
from .filedialogsubmission import render_template


async def handle_file_select_action(*, event_data, action_data, logger, app):
    """Handle the selection from a ``templatebot_file_select`` action ID.

    The key steps are:

    1. Use the ``chat.update`` method to replace the original message
       containing a selection menu with a confirmation message. This prevents
       someone from interacting with the menu again.
    2. Open a Slack dialog to let the user fill in template variables based
       on the ``cookiecutter.json`` file. If the template doens't have any
       variables, then respond with the rendered template immediately instead
       of openening the dialog.
    """
    await _confirm_selection(event_data=event_data, action_data=action_data,
                             logger=logger, app=app)

    selected_template = action_data['selected_option']['value']
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[selected_template]
    if len(template.config['dialog_fields']) == 0:
        await _respond_with_nonconfigurable_content(
            template=template, event_data=event_data, logger=logger,
            app=app)
    else:
        await open_template_dialog(
            template=template, callback_id_root='templatebot_file_dialog',
            event_data=event_data, logger=logger, app=app)


async def _confirm_selection(*, event_data, action_data, logger, app):
    """Confirm the menu selection by replacing the menu with a static message.
    """
    text_content = (
        f"<@{event_data['user']['id']}> :raised_hands: "
        "I'll help you with that "
        f"{action_data['selected_option']['text']['text']} snippet."
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


async def _respond_with_nonconfigurable_content(*, template, event_data,
                                                logger, app):
    """Respond to the user on Slack with the content of a non-configurable
    template.

    This is an alternative pathway to `_open_dialog`.
    """
    channel_id = event_data['channel']['id']
    user_id = event_data['user']['id']
    await render_template(
        template=template,
        template_variables={},
        channel_id=channel_id,
        user_id=user_id,
        logger=logger,
        app=app)
