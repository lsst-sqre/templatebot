### Bug fixes

- Stop cosmetic Slack status updates from discarding project creation. `TemplateService` now routes every `chat.update` progress message through a new `_post_status_update` helper that logs and swallows `httpx.HTTPError` and `SlackApiError`. Previously an `httpx.ReadTimeout` on the opening "I'm creating your new project..." update propagated out of the first statement of `create_project_from_template`, abandoning the user's request before anything had been attempted. GitHub, LSST the Docs, render, and push failures still fail the job as before.
