# Changelog

## Unreleased

- A 429's wait is read from its body when it has no Retry-After header (the edge's rate limit sends none), and a
  wait longer than a minute is raised at once instead of being retried early.
- A 422 says which parameter was wrong and why, instead of "HTTP 422".
- `lookup()` and `person()` refuse an empty argument before calling the API.
- `normalize_ipi()` writes a number the way a writers answer does, to match answers to your list.
- `help()` on a response type lists its fields.

## 0.1.0

First release: `lookup`, `person`, `person_works`, `writers` and `version` over the Songlinks API 0.11.0, typed
answers, typed errors, and retries that honour `Retry-After`.
