"""Handler for the initial interaction where a user wants to see a list of
project templates.
"""

__all__ = ["handle_project_creation"]


async def handle_project_creation(*, event, app, logger):
    """Handle an initial event from a user asking to make a new project
    (typically a GitHub repository).

    Parameters
    ----------
    event : `dict`
        The body of the Slack event.
    app : `aiohttp.web.Application`
        The application instance.
    logger
        A structlog logger, typically with event information already
        bound to it.
    """
    menu_options = _generate_menu_options(app, logger)

    event_channel = event["event"]["channel"]
    calling_user = event["event"]["user"]

    httpsession = app["root"]["api.lsst.codes/httpSession"]
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f'Bearer {app["root"]["templatebot/slackToken"]}',
    }
    body = {
        "token": app["root"]["templatebot/slackToken"],
        "channel": event_channel,
        # Since there are `blocks`, this is a fallback for notifications
        "text": (
            f"<@{calling_user}>, what type of project do you " "want to make?"
        ),
        "blocks": [
            {
                "type": "section",
                "block_id": "templatebot_project_select",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{calling_user}>, what type of project do you "
                        "want to make?"
                    ),
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "templatebot_project_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template",
                        "emoji": True,
                    },
                    "option_groups": menu_options,
                },
            }
        ],
    }
    url = "https://slack.com/api/chat.postMessage"
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
    if not response_json["ok"]:
        logger.error(
            "Got a Slack error from chat.postMessage", contents=response_json
        )


def _generate_menu_options(app, logger):
    repo = app["templatebot/repo"].get_repo(
        gitref=app["root"]["templatebot/repoRef"]
    )
    template_groups = {}
    for template in repo.iter_project_templates():
        group = template.config["group"]
        label = template.config["name"]
        name = template.name
        if group in template_groups:
            template_groups[group][label] = name
        else:
            template_groups[group] = {label: name}

    group_names = sorted(template_groups.keys())
    # Always put 'General' at the beginning
    if "General" in group_names:
        group_names.insert(0, group_names.pop(group_names.index("General")))
    logger.debug("Group names", names=group_names)
    option_groups = []
    for group_name in group_names:
        group = {
            "label": {"type": "plain_text", "text": group_name},
            "options": [],
        }
        option_labels = sorted(template_groups[group_name])
        for label in option_labels:
            name = template_groups[group_name][label]
            option = {
                "text": {"type": "plain_text", "text": label, "emoji": True},
                "value": name,
            }
            group["options"].append(option)
        option_groups.append(group)
    logger.debug("Made option groups", groups=option_groups)
    return option_groups
