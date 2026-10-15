# Optional GTFS CSV health regression

Follow-up to PR1896 and its actual PASS/PASS verifier38818103425. One advisory concern was reproduced against merged source: a valid ZIP with an oversized calendar CSV header/row makes the served `/api/health` return500. The adapter normalizes required-table CSV errors, but the optional-calendar reader did not.

Four new served-endpoint cases cover header and row errors in `calendar.txt` and `calendar_dates.txt`. Unchanged production source at e5d4ec767 produces4 assertion failures (HTTP500 rather than200). Normalizing `csv.Error` to the loader's existing `ValueError` convention produces112 passing health/flight/rail/fetch cases. The response remains200/statusok/database.readytrue, withrail_timetable statusfeed_unreadable and reasonValueError. No field-size limit is raised, feed accepted, or parse error hidden as no trains.

Commands used the canonical repository Python3.14 virtual environment, explicit worktree PYTHONPATH and a private SQLite URL under lane scratch. All raw console and JUnit files are retained here; manifest binds original source, candidate source/tests and evidence. Ruff, scoped mypy and diff-check passed; Black formatted both changed files. These are offline regression proofs, not a new live-provider trial or a replacement deployment observation.
