"""Rendering the initial commit for a GitHub repo with cookiecutter.
"""

__all__ = ('handle_project_render',)


async def handle_project_render(*, event, schema, app, logger):
    """Handle a ``templatebot-render_ready`` event.

    In this event, the GitHub repo has been built, and now we can push the
    first commit based on template content.
    """
    logger.info('In handler_project_render')
