"""Slack handler when a user submits a dialog to create a file.
"""

__all__ = ('handle_file_dialog_submission',)

import json

from templatekit.filerender import render_file_template
import yarl


async def handle_file_dialog_submission(*, event_data, logger, app):
    """Handle the dialog_submission interaction from a
    ``templatebot_file_dialog``.
    """
    channel_id = event_data['channel']['id']
    user_id = event_data['user']['id']
    submission_data = event_data['submission']
    state = json.loads(event_data['state'])

    template_name = state['template_name']
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[template_name]
    logger.debug('template.source_path', path=template.source_path)
    rendered_text = render_file_template(template.source_path,
                                         use_defaults=True,
                                         extra_context=submission_data)

    comment_text = f"<@{user_id}>, here's your file!"

    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    url = 'https://slack.com/api/files.upload'
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channels': channel_id,
        'content': rendered_text,
        'filename': 'demo.txt',
        'filetype': 'text',
        'initial_comment': comment_text,
    }
    encoded_body = yarl.URL.build(query=body).query_string.encode('utf-8')
    async with httpsession.post(url, data=encoded_body, headers=headers) \
            as response:
        response_json = await response.json()
        logger.info(
            'templatebot_file_dialog submission reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from files.upload',
            contents=response_json)
