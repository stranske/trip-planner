import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildFixThreadsReport,
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  isPlaceholderValue,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeUrlFieldValue,
  parseThreadInventory,
} = require(path.join(repoRoot, "scripts/list_fix_threads_from_doc.js"));

test("parseThreadInventory reads structured thread metadata from markdown", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: disposition
- Rationale: Existing behavior is intentional.
- Content: Reviewer asked for a change that would regress issue #176.
`);

  assert.deepEqual(threads, [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:8",
      classification: "disposition",
      followUpPr: null,
      rationale: "Existing behavior is intentional.",
      content: "Reviewer asked for a change that would regress issue #176.",
    },
  ]);
});

test("parseThreadInventory normalizes markdown links for URL fields", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: [review thread](https://github.com/stranske/trip-planner/pull/178#discussion_r1)
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: <https://github.com/stranske/trip-planner/pull/581>
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
`);

  assert.deepEqual(threads, [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
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
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
    },
  ]);

  assert.match(report, /Fix-classified threads: 1/);
  assert.match(report, /1\. THREAD_1/);
  assert.match(
    report,
    /Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/
  );
  assert.match(report, /Location: trip_planner\/example\.py:17/);
  assert.match(report, /Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/);
});

test("collectThreadInventoryIssues flags missing metadata and placeholder entries", () => {
  const issues = collectThreadInventoryIssues([
    {
      threadId: null,
      location: null,
      classification: null,
      followUpPr: null,
      rationale: null,
      content: null,
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:8",
      followUpPr: null,
      classification: "follow-up",
      rationale: "Need product clarification.",
      content: "Reviewer requested a new classification.",
    },
    {
      threadId: "THREAD_3",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r3",
      location: "trip_planner/fix.py:5",
      classification: "fix",
      followUpPr: null,
      rationale: "Code update is required.",
      content: "Reviewer requested a follow-up patch.",
    },
  ]);

  assert.deepEqual(issues, [
    "Thread 1: missing thread ID",
    "Thread 1: missing original thread URL",
    "Thread 1: missing location",
    "Thread 1: missing classification",
    "Thread 1: missing rationale",
    "Thread 1: missing content",
    'THREAD_2: invalid classification "follow-up"',
    "THREAD_3: missing follow-up PR",
  ]);
});

test("placeholder helper recognizes common incomplete values", () => {
  assert.equal(isPlaceholderValue("TBD"), true);
  assert.equal(isPlaceholderValue(" pending "), true);
  assert.equal(isPlaceholderValue("https://github.com/stranske/trip-planner/pull/581"), false);
});

test("normalizeUrlFieldValue unwraps markdown and autolink URLs", () => {
  assert.equal(
    normalizeUrlFieldValue("[PR #581](https://github.com/stranske/trip-planner/pull/581)"),
    "https://github.com/stranske/trip-planner/pull/581"
  );
  assert.equal(
    normalizeUrlFieldValue("<https://github.com/stranske/trip-planner/pull/581>"),
    "https://github.com/stranske/trip-planner/pull/581"
  );
  assert.equal(normalizeUrlFieldValue("TBD"), null);
});

test("collectThreadInventoryIssues treats placeholder text as incomplete metadata", () => {
  const issues = collectThreadInventoryIssues([
    {
      threadId: "THREAD_1",
      originalThreadUrl: null,
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: null,
      rationale: null,
      content: "Reviewer requested a bounds check.",
    },
  ]);

  assert.deepEqual(issues, [
    "THREAD_1: missing original thread URL",
    "THREAD_1: missing follow-up PR",
    "THREAD_1: missing rationale",
  ]);
});

test("formatThreadInventoryIssues summarizes completeness problems", () => {
  const report = formatThreadInventoryIssues([
    "Thread 1: missing thread ID",
    "THREAD_2: invalid classification \"follow-up\"",
  ]);

  assert.match(report, /Thread inventory issues: 2/);
  assert.match(report, /1\. Thread 1: missing thread ID/);
  assert.match(report, /2\. THREAD_2: invalid classification "follow-up"/);
});

test("getCliConfiguration parses completeness validation flag and doc path", () => {
  assert.deepEqual(getCliConfiguration(["docs/custom.md", "--require-complete"]), {
    docPath: path.resolve("docs/custom.md"),
    requireComplete: true,
  });
});

test("getCliConfiguration rejects unknown options and extra positional arguments", () => {
  assert.throws(() => getCliConfiguration(["--unknown"]), /Unknown option: --unknown/);
  assert.throws(
    () => getCliConfiguration(["docs/one.md", "docs/two.md"]),
    /Unexpected argument: docs\/two\.md/
  );
});

test("the checked-in PR #178 inventory is still incomplete until real threads are recorded", () => {
  const threads = loadThreadInventory(DEFAULT_DOC_PATH);
  const issues = collectThreadInventoryIssues(threads);

  assert.equal(issues.length, 24);
  assert.match(formatThreadInventoryIssues(issues), /Thread inventory issues: 24/);
});

test("the checked-in PR #178 inventory currently contains no fix-classified threads", () => {
  const threads = loadThreadInventory(DEFAULT_DOC_PATH);
  const fixThreads = listFixClassifiedThreads(threads);

  assert.equal(fixThreads.length, 0);
});

test("fix-classified entries with follow-up PR links satisfy completeness checks", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
`);

  assert.deepEqual(collectThreadInventoryIssues(threads), []);
});

test("disposition-only entries do not require a follow-up PR to be complete", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Rationale: The requested change would regress the documented behavior.
- Content: Reviewer asked for a change that is intentionally out of scope.
`);

  assert.deepEqual(collectThreadInventoryIssues(threads), []);
});

test("buildFixThreadsReport enforces completeness checks before returning fix threads", () => {
  const markdown = `
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
`;

  const report = buildFixThreadsReport(
    { docPath: "docs/complete.md", requireComplete: true },
    {
      readFileSync: () => markdown,
    }
  );

  assert.match(report, /Fix-classified threads: 1/);
  assert.match(report, /THREAD_1/);
});

test("buildFixThreadsReport surfaces completeness issues when --require-complete would fail", () => {
  assert.throws(
    () =>
      buildFixThreadsReport(
        { docPath: "docs/incomplete.md", requireComplete: true },
        {
          readFileSync: () => `
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
`,
        }
      ),
    /Thread inventory issues: 6/
  );
});
