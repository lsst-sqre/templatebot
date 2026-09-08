### Bug fixes

- A technote submission naming an author ID that isn't in lsst-texmf's `etc/authordb.yaml` now shows the user how to fix it instead of a generic "Sorry, something went wrong" message. The trigger message is replaced, exactly once, with the author ID that wasn't found, a link to the author list spreadsheet, a link to open a pull request against `etc/authordb.yaml`, and a copy of the values that were submitted. Operators get a soft alert naming the author ID rather than an abandoned-creation incident, and the event is logged at warning level as `author_id_not_found`.
