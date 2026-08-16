### Bug fixes

- Raise `templatebot.storage.slack.SlackApiError` when the Slack Web API rejects a call with `{"ok": false}`. Slack reports application-level failures on an HTTP 200, so `raise_for_status` never fires for them; `SlackWebApiClient.post_json` previously only logged the rejection and returned the payload, making a failed `chat.update` indistinguishable from a successful one, and `SlackWebApiClient.get` did not check `ok` at all. Both now raise, and the exception carries the Slack API method, Slack's error code, and the request payload as attributes for structured logging.
