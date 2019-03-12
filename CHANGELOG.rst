##########
Change log
##########

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
