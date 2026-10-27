# Changelog

## 0.2.0

- `songwriters(isrcs)`: who wrote up to 50 recordings, by ISRC (`GET /v1/songwriters`). For each recording, the
  works it is registered to, their writers with role and IPI name number, and each writer's person ID where there is
  one. Typed as `SongwritersResponse`, `RecordingAnswer`, `RecordingWork` and `RecordingWriter`; refuses an empty list,
  more than `SONGWRITERS_MAX` (50) entries, and an entry the API would split, before calling the API.
- `normalize_isrc()` writes an ISRC the way a songwriters answer does (12 characters, upper case, no dashes), to match
  answers to your list.
- `examples/recording_writers.py`: a CSV of ISRCs in, one row per writer out.
- A 429's wait is read from its body when it has no Retry-After header (the edge's rate limit sends none), and a
  wait longer than a minute is raised at once instead of being retried early.
- A 422 says which parameter was wrong and why, instead of "HTTP 422".
- `lookup()` and `person()` refuse an empty argument before calling the API.
- `normalize_ipi()` writes a number the way a writers answer does, to match answers to your list.
- `help()` on a response type lists its fields.

## 0.1.0

First release: `lookup`, `person`, `person_works`, `writers` and `version` over the Songlinks API 0.11.0, typed
answers, typed errors, and retries that honour `Retry-After`.
