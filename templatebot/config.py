"""Configuration collection."""

import os

__all__ = ["create_config"]


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
    c["api.lsst.codes/profile"] = os.getenv(
        "API_LSST_CODES_PROFILE", "development"
    ).lower()

    # That name of the api.lsst.codes service, which is also the root path
    # that the app's API is served from.
    c["api.lsst.codes/name"] = os.getenv("API_LSST_CODES_NAME", "templatebot")

    # The name of the logger, which should also be the name of the Python
    # package.
    c["api.lsst.codes/loggerName"] = os.getenv(
        "API_LSST_CODES_LOGGER_NAME", "templatebot"
    )

    # Log level (INFO or DEBUG)
    c["api.lsst.codes/logLevel"] = os.getenv(
        "API_LSST_CODES_LOG_LEVEL",
        "info" if c["api.lsst.codes/profile"] == "production" else "debug",
    ).upper()

    # Schema Registry hostname (use same config variable as SQRBOTJR)
    c["templatebot/registryUrl"] = os.getenv("REGISTRY_URL")

    # Kafka broker host (use same config variable as SQRBOTJR)
    c["templatebot/brokerUrl"] = os.getenv("KAFKA_BROKER")

    # Kafka security protocol: PLAINTEXT or SSL
    c["templatebot/kafkaProtocol"] = os.getenv("KAFKA_PROTOCOL")

    # Kafka SSL configuration (optional)
    c["templatebot/clusterCaPath"] = os.getenv("KAFKA_CLUSTER_CA")
    c["templatebot/clientCaPath"] = os.getenv("KAFKA_CLIENT_CA")
    c["templatebot/clientCertPath"] = os.getenv("KAFKA_CLIENT_CERT")
    c["templatebot/clientKeyPath"] = os.getenv("KAFKA_CLIENT_KEY")

    # Slack token (use same config variable as SQRBOTJR)
    c["templatebot/slackToken"] = os.getenv("SLACK_TOKEN")

    # Suffix to add to Schema Registry suffix names. This is useful when
    # deploying sqrbot-jr for testing/staging and you do not want to affect
    # the production subject and its compatibility lineage.
    c["templatebot/subjectSuffix"] = os.getenv(
        "TEMPLATEBOT_SUBJECT_SUFFIX", ""
    )

    # Compatibility level to apply to Schema Registry subjects. Use
    # NONE for testing and development, but prefer FORWARD_TRANSITIVE for
    # production.
    c["templatebot/subjectCompatibility"] = os.getenv(
        "TEMPLATEBOT_SUBJECT_COMPATIBILITY", "FORWARD_TRANSITIVE"
    )

    # Template repository (Git URL)
    c["templatebot/repoUrl"] = os.getenv(
        "TEMPLATEBOT_REPO", "https://github.com/lsst/templates"
    )

    # Default Git ref for the template repository ('templatebot/repo')
    c["templatebot/repoRef"] = os.getenv("TEMPLATEBOT_REPO_REF", "main")

    # GitHub token for SQuaRE bot
    c["templatebot/githubToken"] = os.getenv("TEMPLATEBOT_GITHUB_TOKEN")
    c["templatebot/githubUsername"] = os.getenv("TEMPLATEBOT_GITHUB_USER")

    # Topic names
    c["templatebot/prerenderTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_PRERENDER", "templatebot.prerender"
    )
    c["templatebot/renderreadyTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_RENDERREADY", "templatebot.render-ready"
    )
    c["templatebot/postrenderTopic"] = os.getenv(
        "TEMPLATEBOT_TOPIC_POSTRENDER", "templatebot.postrender"
    )
    c["templatebot/appMentionTopic"] = os.getenv(
        "SQRBOTJR_TOPIC_APP_MENTION", "sqrbot.app.mention"
    )
    c["templatebot/messageImTopic"] = os.getenv(
        "SQRBOTJR_TOPIC_MESSAGE_IM", "sqrbot.message.im"
    )
    c["templatebot/interactionTopic"] = os.getenv(
        "SQRBOTJR_TOPIC_INTERACTION", "sqrbot.interaction"
    )

    # Group IDs for the Slack topic consumer and the the templatebot
    # consumer; defaults to the app's name.
    c["templatebot/slackGroupId"] = os.getenv(
        "TEMPLATEBOT_SLACK_GROUP_ID", c["api.lsst.codes/name"]
    )
    c["templatebot/eventsGroupId"] = os.getenv(
        "TEMPLATEBOT_EVENTS_GROUP_ID", c["api.lsst.codes/name"]
    )

    # Enable topic configuration by the app (disable is its being configured
    # externally).
    c["templatebot/enableTopicConfig"] = bool(
        int(os.getenv("TEMPLATEBOT_TOPIC_CONFIG", "1"))
    )
    # Enable the Kafka consumer listening to sqrbot
    c["templatebot/enableSlackConsumer"] = bool(
        int(os.getenv("TEMPLATEBOT_ENABLE_SLACK_CONSUMER", "1"))
    )
    # Enable the Kafka consumer listening to events from the aide
    c["templatebot/enableEventsConsumer"] = bool(
        int(os.getenv("TEMPLATEBOT_ENABLE_EVENTS_CONSUMER", "1"))
    )

    return c
