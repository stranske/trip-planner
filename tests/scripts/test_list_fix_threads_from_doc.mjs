import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_DOC_PATH,
  formatFixThreadsReport,
  listFixClassifiedThreads,
  loadThreadInventory,
  parseThreadInventory,
} = require(path.join(repoRoot, "scripts/list_fix_threads_from_doc.js"));

test("parseThreadInventory reads structured thread metadata from markdown", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Location: trip_planner/example.py:17
- Classification: fix
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.

### Thread 2

- Thread ID: THREAD_2
- Location: trip_planner/other.py:8
- Classification: disposition
- Rationale: Existing behavior is intentional.
- Content: Reviewer asked for a change that would regress issue #176.
`);

  assert.deepEqual(threads, [
    {
      threadId: "THREAD_1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
    },
    {
      threadId: "THREAD_2",
      location: "trip_planner/other.py:8",
      classification: "disposition",
      rationale: "Existing behavior is intentional.",
      content: "Reviewer asked for a change that would regress issue #176.",
    },
  ]);
});

test("listFixClassifiedThreads returns only fix-classified entries", () => {
  const fixThreads = listFixClassifiedThreads([
    { threadId: "THREAD_1", classification: "fix" },
    { threadId: "THREAD_2", classification: "disposition" },
    { threadId: "THREAD_3", classification: null },
  ]);

  assert.deepEqual(fixThreads, [{ threadId: "THREAD_1", classification: "fix" }]);
});

test("formatFixThreadsReport summarizes the filtered fix list", () => {
  const report = formatFixThreadsReport([
    {
      threadId: "THREAD_1",
      location: "trip_planner/example.py:17",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
    },
  ]);

  assert.match(report, /Fix-classified threads: 1/);
  assert.match(report, /1\. THREAD_1/);
  assert.match(report, /Location: trip_planner\/example\.py:17/);
});

test("the checked-in PR #178 inventory currently contains no fix-classified threads", () => {
  const threads = loadThreadInventory(DEFAULT_DOC_PATH);
  const fixThreads = listFixClassifiedThreads(threads);

  assert.equal(fixThreads.length, 0);
});
