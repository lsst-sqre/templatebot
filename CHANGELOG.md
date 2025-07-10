# Change log

<!-- scriv-insert-here -->

<a id='changelog-0.5.1'></a>

## 0.5.1 (2025-07-10)

### Bug fixes

- Fix parsing of the `ror` field from the Ook `/authors/:id` API endpoint.

<a id='changelog-0.5.0'></a>

## 0.5.0 (2025-07-09)

### New features

- Added ability to create the [lsst-texmf](https://github.com/lsst/lsst-texmf) submodule in new LaTeX projects.

<a id='changelog-0.4.0'></a>

## 0.4.0 (2025-07-08)

### New features

- Author information is now retrieved from Ook's `/authors/` API, rather than directly through `authordb.yaml` in https://github.com/lsst/lsst-texmf.
- Improved Slack user feedback when they enter an incorrect author ID, including information on how to find or add an author, and a copy of their original submission for reference.

### Other changes

- Adopt uv.lock for managing dependencies, in conjunction with dependency groups. nox-uv allows us to run nox sessions with uv groups installed. The Docker image build also uses uv to install the project.

<a id='changelog-0.3.0'></a>

## 0.3.0 (2024-10-08)

### New features

- This is an all-new version of templatebot built for the modern Squarebot. It uses Faststream and FastAPI with Pydantic models for modelling the event payloads. Templatebot now also combines the previous templatebot with lsst-templatebot-aide to provide a single backend to handle project bootstrapping for Rubin Observatory projects.

## 0.2.0 (2021-12-01)

- Change PR for lsst-texmf to use main branches, not master.
- Update to GitHub Actions from Travis CI
- Modernize packaging to meet SQuaRE's current standards (tox, pre-commit, formatting with Black and isort, pip-tools compiled dependencies and multi-stage docker image build).

## 0.1.2 (2020-06-30)

- Improve messaging to the Slack user (always "at" the user).

## 0.1.1 (2020-06-15)

- Update aiokafka to 0.6.0.
  This should resolve the uncaught UnknownMemberId exception that was causing the templatebot Kafka consumer to drop its connection to the Kafka brokers.

- Update kafkit to 0.2.0b3.

- Updated testing stack to pytest 5.4.3 and pytest-flake8 to 1.0.6.

- Updated GitPython to 3.1.3 to resolve a floating dependency error related to the `gitdb.utils.compat` module.

- Updated templatekit to 0.4.1, matching the version used by [lsst/templates](https://github.com/lsst/templates). This change also allowed us to float the version of Click so that it would be set by cookiecutter/templatekit.

## 0.1.0 (2019-11-29)

This release focuses on improving the deployment with Kustomize, better configurability, and support for connecting to Kafka brokers through TLS.

- Templatebot can now be deployed through Kustomize. The base is located at `/manifests/base`. This means that you can incorporate this application into a specific Kustomize-based application (such as one deployed by Argo CD) with a URL such as `github.com/lsst-sqre/templatebot.git//manifests/base?ref=0.1.0`. There is a separate template for the Secret resource expected by the deployment at `/manifest/base/secret.template.yaml`.

- Topics names can now be configured directly. See the environment variables:

  - `TEMPLATEBOT_TOPIC_PRERENDER`
  - `TEMPLATEBOT_TOPIC_RENDERREADY`
  - `TEMPLATEBOT_TOPIC_POSTRENDER`
  - `SQRBOTJR_TOPIC_APP_MENTION`
  - `SQRBOTJR_TOPIC_MESSAGE_IM`
  - `SQRBOTJR_TOPIC_INTERACTION`

  This granular configuration allows you to consume production topics, but output development topics, for example.

- The old "staging version" configuration is now the `TEMPLATEBOT_SUBJECT_SUFFIX` environment variable. This configuration is used solely as a suffix on the fully-qualified name of a schema when determining its subject name at the Schema Registry. Previously it also impacted topic names. Use a subject suffix when trying out new Avro schemas to avoid polluting the production subject in the registry.

- Templatebot can now connect to Kafka brokers through SSL. Set the `KAFKA_PROTOCOL` environment variable to `SSL`. Then set these environment variables to the paths of specific TLS certificates and keys:

  - `KAFKA_CLUSTER_CA` (the Kafka cluster's CA certificate)
  - `KAFKA_CLIENT_CA` (Templatebot's client CA certificate)
  - `KAFKA_CLIENT_CERT` (Templatebot's client certificate)
  - `KAFKA_CLIENT_KEY` (Templatebot's client key)

- The consumer group IDs of the sqrbot-topic and templatebot-aide topic consumers can now be set independently with these environment variables:

  - `TEMPLATEBOT_SLACK_GROUP_ID`
  - `TEMPLATEBOT_EVENTS_GROUP_ID`

  It's a good idea to set these consumers to have different groups to avoid apparent race conditions when starting up.

- Individual features can be enabled or disabled:

  - `TEMPLATEBOT_ENABLE_SLACK_CONSUMER`: set to `"0"` to disable consuming events from sqrbot.
  - `TEMPLATEBOT_ENABLE_EVENTS_CONSUMER`: set to `"0"` to disable consuming events from templatebot-aide.
  - `TEMPLATEBOT_TOPIC_CONFIG`: set to `"0"` to disable configuring topics if they do not already exist.

## 0.0.8 (2019-11-04)

- Templatebot now responds to the user typing "help."

## 0.0.7 (2019-11-04)

- Templatebot now routinely checks if the template repository clone is up-to-date with the origin remote.
  These checks are done whenever the template repository is being accessed, for instance in the handlers that list templates, that present template dialogs in Slack, or in rendering a template.
  A template repository is only re-cloned if the local SHA does not match the SHA of the symbolic Git ref (branch or tag) on the origin.

## 0.0.6 (2019-10-14)

- Update templatekit to 0.3.0.

## 0.0.5 (2019-05-02)

- Templatebot now uses the `master` branch of https://github.com/lsst/templates by default.

- Templatebot now responds to `app_mention` Slack events. This means that you can be in a public channel and type `@sqrbot-jr create file`. Templatebot continues to monitor direct messages.

## 0.0.4 (2019-04-16)

This release builds out the ability for Templatebot to trigger pre- and post-rendering events to domain-specific helper applications. For LSST, this helper microservice is [lsst-templatebot-aide](https://github.com/lsst-sqre/lsst-templatebot-aide). The sequence of events is:

1. Templatebot receives the `sqrbot-interaction` event from Slack dialog closure for files or projects. For project templates, Templatebot emits a `templatebot-prerender` event that gets picked up by the `lsst-templatebot-aide` or equivalent external microservice.

2. The helper microservice provisions the repository on GitHub. This allows a helper to do specialized work to select and provision a GitHub repository. For example, to determine the serial number for a template's repository. The helper emits a `templatebot-render_ready` event.

3. Templatebot creates the first commit for the new repository based on the Cookiecutter template and then emits a `templatebot-postrender` event.

4. The helper application receives the `templatebot-postrender` event and does additional configuration, such as activating CI and documentation services.

This release also includes Kubernetes deployment manifests.

## 0.0.3 (2019-03-18)

This release focuses on refining the user experience of creating a file or project from Slack using the `templatekit.yaml` configuration files introduced in Templatekit 0.2.0.

- In the initial template selection menus, template names and groupings are derived from `templatekit.yaml` configurations. Templates are now better organized and better labeled!

- Fields in the dialog are driven by the `dialog_fields` field in `templatekit.yaml` configurations (Templatekit will still provide a default set of fields if none are set). These configurations, defined in Templatekit 0.2.0+ allow for exciting UI features like labels, placeholders, and hints. The schema validator in Templatekit ensures that labels aren't too long, and that there aren't too many dialog fields — this makes the dialog implementation in Templatebot much simpler.

  These configurations also introduce the concept of _preset menus_, which combine multiple cookiecutter variable presets into selection menu options. This feature lets us handle complicated templates, which many boolean or constrained option variables, within the five-field limit imposed by Slack dialogs.

- This release also includes a handler for project templates, though only as a proof-of-concept for showing that cookiecutter variables for complex templates like `stack_package` can be successfully captured.

## 0.0.2 (2019-03-12)

This release focuses on file template creation (`@sqrbot-jr create file`):

- A new `RepoManager` class manages clones of the template repository (a Git repo). The `RepoManager` caches clones by Git SHA and clones are immutable. What this means is that one handler can be rendering a template from the `master` branch while a new handler sees that `master` is updated and begins a new clone of `master`.

- The file template handler now populates the Slack dialog with actual fields from the template's `cookiecutter.json` file and renders the actual template with templatekit. The filename is also rendered from the cookiecutter context.

## 0.0.1 (2019-02-21)

This is the initial proof-of-concept of Templatebot. It implements a SQuaRE Events (Kafka) listener and mocks up an interaction with a Slack-based user creating a file template. Templatebot opens a Slack dialog to get specific information needed by a template, and then uploads the generated file back to the channel. [See this PR for a demo gif](https://github.com/lsst-sqre/templatebot/pull/1#issuecomment-466219231).
