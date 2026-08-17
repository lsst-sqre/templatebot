### New features

- Optionally alert operators in Slack when a creation is abandoned, so the failure is a push signal rather than something to notice in the logs. Set `TEMPLATEBOT_SLACK_ALERT_WEBHOOK` to a Slack incoming webhook URL and each abandoned creation posts a message naming the template, the type, the channel, the user, and the exception — enough to recreate the request by hand. Alerting is off when the variable is unset, and Safir's `SlackWebhookClient` logs and swallows its own errors, so an alert can never become a second failure on the failure path.

### Bug fixes

- Stop dropping project and file creation requests when an outbound Slack call fails. A slow `chat.update` raised an uncaught `httpx.ReadTimeout` out of the very first statement of `TemplateService.create_project_from_template`, discarding a user's technote request with no repository, no error message, and no Kafka redelivery. Four changes close that hole:

   - Retry transient failures on Slack Web API calls. `SlackWebApiClient.post_json` and `SlackWebApiClient.get` now route their requests through a new `templatebot.storage.retry.retry_async` helper, which makes up to three attempts, treats connection failures, timeouts, 5xx responses, and 429 responses as transient, honors a `Retry-After` header, backs off exponentially with jitter, and logs each retry. httpx's own transport-level retries only cover connection errors, so a `ReadTimeout` waiting on a slow Slack response was previously fatal. Retries stay opt-in per call site: the GitHub and LSST the Docs clients create real side effects with their POSTs and deliberately do not use the helper.

   - Raise `templatebot.storage.slack.SlackApiError` when the Slack Web API rejects a call with `{"ok": false}`. Slack reports application-level failures on an HTTP 200, so `raise_for_status` never fires for them; `SlackWebApiClient.post_json` previously only logged the rejection and returned the payload, making a failed `chat.update` indistinguishable from a successful one, and `SlackWebApiClient.get` did not check `ok` at all. Both now raise, and the exception carries the Slack API method, Slack's error code, and the request payload as attributes for structured logging.

   - Stop cosmetic Slack status updates from discarding project creation. `TemplateService` now routes every `chat.update` progress message through a new `_post_status_update` helper that logs and swallows `httpx.HTTPError` and `SlackApiError`. GitHub, LSST the Docs, render, and push failures still fail the job as before.

   - Report abandoned project and file creation instead of dropping it silently. `SlackViewService` now wraps its dispatch to `TemplateService` in a `try`/`except` that logs a structured `project_creation_abandoned` event naming the template, channel, message timestamp, user, and exception type; tells the user in Slack with a `chat.update` on the trigger message, falling back to a new `chat.postMessage` in the same channel if that update fails after its retries; and then re-raises so FastStream still logs the traceback. Previously a failure anywhere inside `create_project_from_template` (a GitHub outage while assigning a technote serial, for instance) left the user with nothing at all.

### Other changes

- Include the repository URL in the `slack_status_update_failed` log event for the final "Your new project is ready!" summary. That update is the one swallowed failure that costs the user something, so the operator now has the URL to hand over.

- Record in `handlers/kafka.py` why the view-submission consumer keeps FastStream's default `ACK_FIRST` (at-most-once) acknowledgement. `create_project_from_template` is not idempotent, so a redelivery would claim a second technote serial through `_assign_technote_repo_serial` and could create a duplicate GitHub repository; the new `project_creation_abandoned` marker log is the operator's recovery path instead.

- Close Safir's `http_client_dependency` in the application lifespan. The operator alert client is templatebot's first user of that dependency, and its HTTP client is separate from the one held by the process context.
