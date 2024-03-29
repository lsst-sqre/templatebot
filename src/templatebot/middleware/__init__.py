"""aiohttp.web middleware for the application."""

from .logging import bind_logger

__all__ = ["setup_middleware"]


def setup_middleware(app):
    """Add middleware to the application.

    Notes
    -----
    This function includes the following middleware, in order:

    1. `templatebot.middleware.bind_logger`

    Examples
    --------
    Use it like this:

    .. code-block:: python

       app = web.Application()
       setup_middleware(app)
    """
    app.middlewares.append(bind_logger)
