"""Rendering the initial commit for a GitHub repo with cookiecutter.
"""

__all__ = ('handle_project_render',)

import copy
import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.parse

from cookiecutter.main import cookiecutter
import git

from templatebot.slack.chat import post_message
from templatebot.slack.users import get_user_info
from templatebot import github


async def handle_project_render(*, event, schema, app, logger):
    """Handle a ``templatebot-render_ready`` event.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-prerender`` event's message.
    schema : `dict`
        The Avro schema corresponding to the ``event``.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Notes
    -----
    In this event, the GitHub repo has been built, and now we can push the
    first commit based on template content.
    """
    logger.info('In handler_project_render')

    template_name = event['template_name']
    template_repo_ref = event['template_repo_ref']
    repo = app['templatebot/repo'].get_repo(template_repo_ref)
    template = repo[template_name]

    # The comitter is the bot
    github_user = await github.get_authenticated_user(app=app, logger=logger)
    committer_actor = git.Actor(github_user['name'], github_user['email'])

    # If possible, associate the author with the requestor on Slack
    if event['slack_username'] is not None:
        user_info = await get_user_info(
            user=event['slack_username'], app=app, logger=logger)
        real_name = user_info['user']['real_name']
        email = user_info['user']['profile']['email']
        author_actor = git.Actor(real_name, email)
    else:
        author_actor = committer_actor

    with TemporaryDirectory() as tmpdir:
        # Render the project with cookiecutter
        cookiecutter(
            str(template.path),
            output_dir=tmpdir,
            overwrite_if_exists=True,
            no_input=True,
            extra_context=event['variables'])
        logger.debug('Rendered cookiecutter project')

        # Find the rendered directory. The actual name is templated so its
        # easier to just find it.
        subdirs = [x for x in Path(tmpdir).iterdir() if x.is_dir()]
        if len(subdirs) > 1:
            logger.warning(
                'Found an unexpected number of possible repo dirs',
                dirs=subdirs)
        repo_dir = subdirs[0]

        # Initialize the GitHub repo
        repo = git.Repo.init(str(repo_dir))
        repo.index.add(repo.untracked_files)

        repo.index.commit("Initial commit",
                          author=author_actor,
                          committer=committer_actor)

        # Modify the repo URL to include auth info in the netloc
        # <user>:<token>@github.com
        bottoken = app['root']['templatebot/githubToken']
        botuser = app['root']['templatebot/githubUsername']
        repo_url_parts = urllib.parse.urlparse(event['github_repo'])
        authed_repo_url_parts = list(repo_url_parts)
        # The [1] index is the netloc.
        authed_repo_url_parts[1] = f'{botuser}:{bottoken}@{repo_url_parts[1]}'
        repo_url = urllib.parse.urlunparse(authed_repo_url_parts)

        # Push the GitHub repo
        origin = repo.create_remote("origin", url=repo_url)
        try:
            origin.push(refspec="master:master")
        except git.exc.GitCommandError:
            logger.exception('Error pushing to GitHub origin',
                             origin_url=event['github_repo'])
            if event['slack_username'] is not None:
                await post_message(
                    text=f"<@{event['slack_username']}>, oh no! "
                         ":slightly_frowning_face:, something went wrong when "
                         "I tried to push the initial Git commit to "
                         f"{event['github_repo']}.\n\nI can't do anything to "
                         "fix it. Could you ask someone at SQuaRE to look "
                         "into it?",
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )
            # TODO: add a few retries here for cases GitHub itself doesn't
            # see its own repo yet.
            raise

        await post_message(
            text=f"<@{event['slack_username']}>, I've pushed the first commit "
                 f"to {event['github_repo']}. You can start working on it!\n\n"
                 "If I have any extra work to do I'll send a PR and let you "
                 "know in this thread.",
            channel=event['slack_channel'],
            thread_ts=event['slack_thread_ts'],
            logger=logger,
            app=app
        )

        logger.info(
            'Pushed to GitHub origin',
            origin_url=event['github_repo'])

        # Send the postrender event
        # First, copy and reset the event based on render_ready
        postrender_payload = copy.deepcopy(event)
        postrender_payload['retry_count'] = 0
        now = datetime.datetime.now(datetime.timezone.utc)
        postrender_payload['initial_timestamp'] = now

        serializer = app['templatebot/eventSerializer']
        postrender_data = await serializer.serialize(
            'templatebot.postrender_v1', postrender_payload)
        producer = app['templatebot/producer']
        topic_name = app['root']['templatebot/postrenderTopic']
        await producer.send_and_wait(topic_name, postrender_data)
        logger.debug(
            'Sent postrender event',
            postrender_topic=topic_name,
            payload=postrender_payload)
