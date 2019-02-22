##########
Change log
##########

0.0.1 (2019-02-21)
==================

This is the initial proof-of-concept of Templatebot.
It implements a SQuaRE Events (Kafka) listener and mocks up an interaction with a Slack-based user creating a file template.
Templatebot opens a Slack dialog to get specific information needed by a template, and then uploads the generated file back to the channel. `See this PR for a demo gif <https://github.com/lsst-sqre/templatebot/pull/1#issuecomment-466219231>`__.

:jirab:`DM-17865`
