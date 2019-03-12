"""Slack handler when a user submits a dialog to create a file.
"""

__all__ = ('handle_file_dialog_submission', 'render_template',)

import os.path
import json

import jinja2
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

    await render_template(
        template=template,
        template_variables=submission_data,
        channel_id=channel_id,
        user_id=user_id,
        logger=logger,
        app=app)


async def render_template(*, template, template_variables, channel_id, user_id,
                          logger, app):
    """Render the file template given the user submission and respond with
    a Slack file upload.
    """
    logger.debug('template.source_path', path=template.source_path)
    rendered_text = render_file_template(template.source_path,
                                         use_defaults=True,
                                         extra_context=template_variables)
    rendered_filename = compute_filename(template=template,
                                         template_variables=template_variables,
                                         logger=logger)

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
        'filename': rendered_filename,
        'title': rendered_filename,
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


def compute_filename(*, template, template_variables, logger):
    """Compute the name of a file given the templated named.
    """
    context = {
        'cookiecutter': template_variables
    }

    if template.source_path.endswith('.jinja'):
        template_str = os.path.basename(
            os.path.splitext(template.source_path)[0])
    else:
        template_str = os.path.basename(template.source_path)
    filename_template = jinja2.Template(template_str)

    filename = filename_template.render(context)
    logger.debug(
        'Rendered file template filename',
        filename=filename, context=context,
        filename_template=template_str)
    return filename
