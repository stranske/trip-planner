# Rail #1891 original acceptance closeout

The full JSON `report.json` preserves the completed 28/28 trial on the official
Amtrak GTFS ZIP for October 20 and 24, 2026. It contains every served and independent
answer, station/time/date text, journey metrics, absence and comparison result.
Each date first passed the independent probe’s nonempty verified rail-service
calendar requirement. A fresh disposable database contained synthetic trips only.

`manifest.json` binds the report, downloaded feed and accepted rail source/probe/test
bytes to head9757d6a5 and actual squash536a9bee, whose complete Git trees are identical.
The public ZIP remains retained locally (18MB) rather than duplicating it in Git.
The follow-up also formats two existing rail files required by the full Black gate;
the manifest separately binds accepted and follow-up bytes and records AST equivalence.
The report is historical captured evidence, not a fixture or a newly asserted provider
PASS. The feed URL is mutable: a later download may have a different hash/timetable.

The exact existing probe command, from an archive of the accepted head with its
root explicitly selected by PYTHONPATH, was:

```sh
python scripts/probe_rail_timetable.py amtrak-GTFS.zip \
  --date 2026-10-20 --date 2026-10-24 --report report.json
```

The initial invocation without explicit PYTHONPATH imported the environment’s
editable main checkout and failed before its trial. It is excluded from proof.
The qualifying exact-head run exited0 and reported28/28, with reportSHA256 recorded
in the manifest and PR1891comment6200661636.

Actual post-merge comparison38796969460/comment6201028707 returned
CONCERNS/CONCERNS (NON_PASS), citing truncated code and inaccessible evidence.
Those verdicts remain unchanged. This follow-up makes the completed trial inspectable
and reconciles the stale9/11 checklist. It also addresses the concrete fixed-partial
fetch-helper finding. Production deployment/feed installation remains separate;
no live server or credential configuration changes are included.


## Fetch-helper follow-up validation

Four offline publication/cleanup/overlap cases reproduce two failures on the exact
original merged helper. `fetch-original-red.xml` retains those two failures and two
passing controls. The repaired helper plus existing rail wiring/adapter suites pass
86 tests (`fetch-and-rail-green.xml`). It uses a unique same-directory temporary file,
validates before atomic replacement and cleans only its own temporary path in finally.
An overlapping invocation can complete without consuming another invocation's partial.

`fetch-real-file.json` records a separate successful run of the repaired actual helper
against the retained original public ZIP through a local file URL:647 stations,
2169 rail trips, calendar present,18,879,584 published bytes and no remaining partials.
No second provider download or production configuration was needed.

Ruff and focused fetch-helper mypy pass. The first full Black check found two
pre-existing formatting failures in this same rail lineage; both are formatted here,
with AST equivalence recorded rather than pretending accepted input hashes are unchanged.
