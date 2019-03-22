"""Rendering the initial commit for a GitHub repo with cookiecutter.
"""

__all__ = ('handle_project_render',)

from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.parse

from cookiecutter.main import cookiecutter
import git


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

        committer = git.Actor("Jonathan Sick",
                              "jsick@lsst.org")
        repo.index.commit("Initial commit",
                          author=committer,
                          committer=committer)

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

        logger.info(
            'Pushed to GitHub origin',
            origin_url=event['github_repo'])
