"""Kafka topic configuration for Templatebot's own topics."""

import structlog
from confluent_kafka.admin import AdminClient, NewTopic

__all__ = ["configure_topics"]


def configure_topics(app):
    """Create Kafka topics for templatebot.

    This function is generally called at app startup.

    Parameters
    ----------
    app : `aiohttp.web.Application`
        The application instance.

    Notes
    -----
    This function registers any templatebot-specific topics that don't already
    exist. The topics correspond one-to-one with schemas in
    ``templatebot/events/schemas/``.

    Access topic names from the root application instance with these keys:

    - ``templatebot/prerenderTopic``
    - ``tempatebot/renderreadyTopic``
    - ``templatebot/postrenderTopic``
    """
    logger = structlog.get_logger(app["root"]["api.lsst.codes/loggerName"])

    default_num_partitions = 1
    default_replication_factor = 3

    client = AdminClient(
        {"bootstrap.servers": app["root"]["templatebot/brokerUrl"]}
    )

    # Set up topic names
    topic_keys = (
        "templatebot/prerenderTopic",
        "templatebot/renderreadyTopic",
        "templatebot/postrenderTopic",
    )

    # First list existing topics
    metadata = client.list_topics(timeout=10)
    existing_topic_names = [t for t in metadata.topics.keys()]

    # Create any topics that don't already exist
    new_topics = []
    for key in topic_keys:
        topic_name = app["root"][key]
        if topic_name in existing_topic_names:
            topic = metadata.topics[topic_name]
            partitions = [p for p in iter(topic.partitions.values())]
            logger.info(
                "Topic exists",
                topic=topic_name,
                partitions=len(topic.partitions),
                replication_factor=len(partitions[0].replicas),
            )
            continue
        new_topics.append(
            NewTopic(
                topic_name,
                num_partitions=default_num_partitions,
                replication_factor=default_replication_factor,
            )
        )

    if len(new_topics) > 0:
        fs = client.create_topics(new_topics)
        for topic_name, f in fs.items():
            try:
                f.result()  # The result itself is None
                logger.info(
                    "Created topic",
                    topic=topic_name,
                    partitions=default_num_partitions,
                )
            except Exception as e:
                logger.error(
                    "Failed to create topic", topic=topic_name, error=str(e)
                )
                raise
