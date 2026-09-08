### Bug fixes

- A technote submission naming an author ID that isn't in lsst-texmf's `etc/authordb.yaml` now shows the user how to fix it instead of a generic "Sorry, something went wrong" message. The trigger message is replaced, exactly once, with the author ID that wasn't found, a link to the author list spreadsheet, a link to open a pull request against `etc/authordb.yaml`, and a copy of the values that were submitted. Operators get a soft alert naming the author ID rather than an abandoned-creation incident, and the event is logged at warning level as `author_id_not_found`.
- An author database that can't be reached at all now gets its own message, asking the user to try again later and handing back the values they submitted, rather than sending them off to check an author ID that is probably fine. Operators still get the full abandoned-creation alert for this case, since an outage is a real incident.

### Other changes

- Author lookups against Ook now retry transient failures — 5xx responses, connection errors, and timeouts — before giving up, so a brief hiccup no longer costs a user their submission.
