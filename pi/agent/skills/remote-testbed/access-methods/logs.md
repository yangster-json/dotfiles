# Remote firmware logs

This workflow is read-only. First classify the platform in RAS, then read the
matching platform access-method reference. For the full bounded archive-search
procedure, use the existing `remote-testbed-logs` skill while preserving the
RAS-derived endpoint and connection route.

Do not recursively search a remote filesystem or mutate testbed state while
collecting logs.
