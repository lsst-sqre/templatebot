"""Handle a project_dialog_submission event after the user has filled out
a dialog with template configuration.
"""

__all__ = ('handle_project_dialog_submission',)

import json

from templatebot.slack.dialog import post_process_dialog_submission


async def handle_project_dialog_submission(*, event_data, logger, app):
    """Handle the dialog_submission interaction from a
    ``templatebot_project_dialog``.
    """
    channel_id = event_data['channel']['id']
    user_id = event_data['user']['id']
    state = json.loads(event_data['state'])

    template_name = state['template_name']
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[template_name]

    template_variables = post_process_dialog_submission(
        submission_data=event_data['submission'],
        template=template)
    logger.info(
        'project dialog submission',
        variables=template_variables,
        template=template.name,
        user_id=user_id,
        channel_id=channel_id)
