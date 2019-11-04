##########
Change log
##########

0.0.7 (2019-11-04)
==================

- Templatebot now routinely checks if the template repository clone is up-to-date with the origin remote.
  These checks are done whenever the template repository is being accessed, for instance in the handlers that list templates, that present template dialogs in Slack, or in rendering a template.
  A template repository is only re-cloned if the local SHA does not match the SHA of the symbolic Git ref (branch or tag) on the origin.

0.0.6 (2019-10-14)
==================

- Update templatekit to 0.3.0.

0.0.5 (2019-05-02)
==================

- Templatebot now uses the ``master`` branch of https://github.com/lsst/templates by default.

- Templatebot now responds to ``app_mention`` Slack events.
  This means that you can be in a public channel and type ``@sqrbot-jr create file``.
  Templatebot continues to monitor direct messages.

0.0.4 (2019-04-16)
==================

This release builds out the ability for Templatebot to trigger pre- and post-rendering events to domain-specific helper applications.
For LSST, this helper microservice is `lsst-templatebot-aide <https://github.com/lsst-sqre/lsst-templatebot-aide>`__.
The sequence of events is:

1. Templatebot receives the ``sqrbot-interaction`` event from Slack dialog closure for files or projects.
   For project templates, Templatebot emits a ``templatebot-prerender`` event that gets picked up by the ``lsst-templatebot-aide`` or equivalent external microservice.

2. The helper microservice provisions the repository on GitHub.
   This allows a helper to do specialized work to select and provision a GitHub repository.
   For example, to determine the serial number for a template's repository.
   The helper emits a ``templatebot-render_ready`` event.

3. Templatebot creates the first commit for the new repository based on the Cookiecutter template and then emits a ``templatebot-postrender`` event.

4. The helper application receives the ``templatebot-postrender`` event and does additional configuration, such as activating CI and documentation services.

This release also includes Kubernetes deployment manifests.

0.0.3 (2019-03-18)
==================

This release focuses on refining the user experience of creating a file or project from Slack using the ``templatekit.yaml`` configuration files introduced in Templatekit 0.2.0.

- In the initial template selection menus, template names and groupings are derived from ``templatekit.yaml`` configurations.
  Templates are now better organized and better labeled!

- Fields in the dialog are driven by the ``dialog_fields`` field in ``templatekit.yaml`` configurations (Templatekit will still provide a default set of fields if none are set).
  These configurations, defined in Templatekit 0.2.0+ allow for exciting UI features like labels, placeholders, and hints.
  The schema validator in Templatekit ensures that labels aren't too long, and that there aren't too many dialog fields — this makes the dialog implementation in Templatebot much simpler.

  These configurations also introduce the concept of *preset menus*, which combine multiple cookiecutter variable presets into selection menu options.
  This feature lets us handle complicated templates, which many boolean or constrained option variables, within the five-field limit imposed by Slack dialogs.

- This release also includes a handler for project templates, though only as a proof-of-concept for showing that cookiecutter variables for complex templates like ``stack_package`` can be successfully captured.

0.0.2 (2019-03-12)
==================

This release focuses on file template creation  (``@sqrbot-jr create file``):

- A new ``RepoManager`` class manages clones of the template repository (a Git repo).
  The ``RepoManager`` caches clones by Git SHA and clones are immutable.
  What this means is that one handler can be rendering a template from the ``master`` branch while a new handler sees that ``master`` is updated and begins a new clone of ``master``.

- The file template handler now populates the Slack dialog with actual fields from the template's ``cookiecutter.json`` file and renders the actual template with templatekit.
  The filename is also rendered from the cookiecutter context.

0.0.1 (2019-02-21)
==================

This is the initial proof-of-concept of Templatebot.
It implements a SQuaRE Events (Kafka) listener and mocks up an interaction with a Slack-based user creating a file template.
Templatebot opens a Slack dialog to get specific information needed by a template, and then uploads the generated file back to the channel. `See this PR for a demo gif <https://github.com/lsst-sqre/templatebot/pull/1#issuecomment-466219231>`__.

:jirab:`DM-17865`
