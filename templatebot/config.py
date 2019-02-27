"""Configuration collection.
"""

__all__ = ('create_config',)

import os


def create_config():
    """Create a config mapping from defaults and environment variable
    overrides.

    Returns
    -------
    c : `dict`
        A configuration dictionary.

    Examples
    --------
    Apply the configuration to the aiohttp.web application::

        app = web.Application()
        app.update(create_config)
    """
    c = {}

    # Application run profile. 'development' or 'production'
    c['api.lsst.codes/profile'] = os.getenv(
        'API_LSST_CODES_PROFILE',
        'development').lower()

    # That name of the api.lsst.codes service, which is also the root path
    # that the app's API is served from.
    c['api.lsst.codes/name'] = os.getenv('API_LSST_CODES_NAME', 'templatebot')

    # The name of the logger, which should also be the name of the Python
    # package.
    c['api.lsst.codes/loggerName'] = os.getenv(
        'API_LSST_CODES_LOGGER_NAME', 'templatebot')

    # Log level (INFO or DEBUG)
    c['api.lsst.codes/logLevel'] = os.getenv(
        'API_LSST_CODES_LOG_LEVEL',
        'info' if c['api.lsst.codes/profile'] == 'production' else 'debug'
    ).upper()

    # Schema Registry hostname (use same config variable as SQRBOTJR)
    c['templatebot/registryUrl'] = os.getenv('SQRBOTJR_REGISTRY')

    # Kafka broker host (use same config variable as SQRBOTJR)
    c['templatebot/brokerUrl'] = os.getenv('SQRBOTJR_BROKER')

    # Slack token (use same config variable as SQRBOTJR)
    c['templatebot/slackToken'] = os.getenv('SQRBOTJR_TOKEN')

    # Version name for Kafka topics, if application is running in a staging
    # environment. This functions similarly to $SQRBOTJR_STAGING_VERSION but
    # it's an independent configuration so that templatebot can be developed
    # independently of sqrbot.
    c['templatebot/topicsVersion'] = os.getenv('TEMPLATEBOT_TOPICS_VERSION') \
        or ''

    # Template repository (Git URL)
    c['templatebot/repoUrl'] = os.getenv(
        'TEMPLATEBOT_REPO',
        'https://github.com/lsst/templates')

    # Default Git ref for the template repository ('templatebot/repo')
    c['templatebot/repoRef'] = os.getenv(
        'TEMPLATEBOT_REPO_REF',
        'master')

    return c
