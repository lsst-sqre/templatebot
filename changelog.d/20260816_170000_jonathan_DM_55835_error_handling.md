### Bug fixes

- Report abandoned project and file creation instead of dropping it silently. `SlackViewService` now wraps its dispatch to `TemplateService` in a `try`/`except` that logs a structured `project_creation_abandoned` event naming the template, channel, message timestamp, user, and exception type; tells the user in Slack with a `chat.update` on the trigger message, falling back to a new `chat.postMessage` in the same channel if that update fails after its retries; and then re-raises so FastStream still logs the traceback. Previously a failure anywhere inside `create_project_from_template` — a GitHub outage while assigning a technote serial, for instance — discarded the request with no repository, no error message, and no Kafka redelivery.
- Include the repository URL in the `slack_status_update_failed` log event for the final "Your new project is ready!" summary. That update is the one swallowed failure that costs the user something, so the operator now has the URL to hand over.

### Other changes

- Record in `handlers/kafka.py` why the view-submission consumer keeps FastStream's default `ACK_FIRST` (at-most-once) acknowledgement. `create_project_from_template` is not idempotent, so a redelivery would burn a second technote serial through `_assign_technote_repo_serial` and could create a duplicate GitHub repository; the new `project_creation_abandoned` marker log is the operator's recovery path instead.
