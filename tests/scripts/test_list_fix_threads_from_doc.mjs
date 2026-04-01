import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildSuggestedBranchName,
  buildFixThreadsReport,
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  formatFixThreadsAsJson,
  formatFixThreadsAsMarkdown,
  formatFixThreadsOutput,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  isPlaceholderValue,
  listActionableFixThreads,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeOutdatedFieldValue,
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
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: disposition
- Rationale: Existing behavior is intentional.
- Content: Reviewer asked for a change that would regress issue #176.
- Outdated: yes
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
      outdated: false,
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:8",
      classification: "disposition",
      followUpPr: null,
      rationale: "Existing behavior is intentional.",
      content: "Reviewer asked for a change that would regress issue #176.",
      outdated: true,
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
- Outdated: no
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
      outdated: false,
    },
  ]);
});

test("parseThreadInventory folds wrapped rationale and content lines into the same field", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code path still drops the final stop when the
  final segment arrives without a cached bounds object.
- Content: Reviewer requested a bounds check before appending
  the last stop to the itinerary response.
- Outdated: no
`);

  assert.deepEqual(threads, [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale:
        "Code path still drops the final stop when the final segment arrives without a cached bounds object.",
      content:
        "Reviewer requested a bounds check before appending the last stop to the itinerary response.",
      outdated: false,
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

test("listActionableFixThreads can exclude outdated fix-classified entries", () => {
  const fixThreads = listActionableFixThreads(
    [
      { threadId: "THREAD_1", classification: "fix", outdated: false },
      { threadId: "THREAD_2", classification: "fix", outdated: true },
      { threadId: "THREAD_3", classification: "disposition", outdated: false },
    ],
    { excludeOutdated: true }
  );

  assert.deepEqual(fixThreads, [{ threadId: "THREAD_1", classification: "fix", outdated: false }]);
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
      outdated: false,
    },
  ]);

  assert.match(report, /Fix-classified threads: 1/);
  assert.match(report, /1\. THREAD_1/);
  assert.match(report, /Suggested Branch: pr-178-fix\/trip-planner-example-py-17-thread-1/);
  assert.match(
    report,
    /Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/
  );
  assert.match(report, /Location: trip_planner\/example\.py:17/);
  assert.match(report, /Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/);
  assert.match(report, /Outdated: no/);
});

test("formatFixThreadsReport includes excluded outdated fix-thread counts when provided", () => {
  const report = formatFixThreadsReport([], { excludedOutdatedCount: 2 });

  assert.match(report, /Fix-classified threads: 0/);
  assert.match(report, /Excluded outdated fix threads: 2/);
});

test("formatFixThreadsAsJson emits machine-readable fix-thread metadata", () => {
  const report = formatFixThreadsAsJson([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
      outdated: false,
    },
  ]);

  const parsed = JSON.parse(report);
  assert.equal(parsed.count, 1);
  assert.equal(parsed.fixThreads[0].threadId, "THREAD_1");
  assert.equal(
    parsed.fixThreads[0].suggestedBranch,
    "pr-178-fix/trip-planner-example-py-17-thread-1"
  );
  assert.equal(
    parsed.fixThreads[0].followUpPr,
    "https://github.com/stranske/trip-planner/pull/581"
  );
  assert.equal(parsed.excludedOutdatedCount, 0);
});

test("formatFixThreadsAsMarkdown emits an actionable fix scope checklist", () => {
  const report = formatFixThreadsAsMarkdown([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Fix-Classified Thread Scope/);
  assert.match(report, /Fix-classified threads: 1/);
  assert.match(report, /## Fix Thread 1/);
  assert.match(report, /- \[ \] Address thread `THREAD_1`/);
  assert.match(report, /- Suggested Branch: `pr-178-fix\/trip-planner-example-py-17-thread-1`/);
  assert.match(
    report,
    /- Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/
  );
  assert.match(report, /- Location: trip_planner\/example\.py:17/);
  assert.match(report, /- Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/);
  assert.match(report, /- Rationale: Code path still drops the final stop\./);
  assert.match(report, /- Content: Reviewer requested a bounds check\./);
  assert.match(report, /- Outdated: no/);
});

test("formatFixThreadsAsMarkdown reports excluded outdated fix threads", () => {
  const report = formatFixThreadsAsMarkdown([], { excludedOutdatedCount: 1 });

  assert.match(report, /Excluded outdated fix threads: 1/);
  assert.match(report, /No fix-classified threads found\./);
});

test("formatFixThreadsOutput dispatches to the requested formatter", () => {
  const fixThreads = [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Code path still drops the final stop.",
      content: "Reviewer requested a bounds check.",
      outdated: false,
    },
  ];

  assert.match(formatFixThreadsOutput(fixThreads, "text"), /Fix-classified threads: 1/);
  assert.doesNotThrow(() => JSON.parse(formatFixThreadsOutput(fixThreads, "json")));
  assert.match(formatFixThreadsOutput(fixThreads, "markdown"), /# Fix-Classified Thread Scope/);
});

test("buildSuggestedBranchName derives a stable feature branch from location and thread id", () => {
  assert.equal(
    buildSuggestedBranchName(
      {
        threadId: "THREAD_1",
        location: "trip_planner/example.py:17",
      },
      0
    ),
    "pr-178-fix/trip-planner-example-py-17-thread-1"
  );

  assert.equal(
    buildSuggestedBranchName(
      {
        threadId: null,
        location: null,
      },
      1
    ),
    "pr-178-fix/thread-2-thread-2"
  );
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
      outdated: null,
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:8",
      followUpPr: null,
      classification: "follow-up",
      rationale: "Need product clarification.",
      content: "Reviewer requested a new classification.",
      outdated: "later",
    },
    {
      threadId: "THREAD_3",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r3",
      location: "trip_planner/fix.py:5",
      classification: "fix",
      followUpPr: null,
      rationale: "Code update is required.",
      content: "Reviewer requested a follow-up patch.",
      outdated: false,
    },
  ]);

  assert.deepEqual(issues, [
    "Thread 1: missing thread ID",
    "Thread 1: missing original thread URL",
    "Thread 1: missing location",
    "Thread 1: missing classification",
    "Thread 1: missing rationale",
    "Thread 1: missing content",
    "Thread 1: missing outdated status",
    'THREAD_2: invalid classification "follow-up"',
    'THREAD_2: invalid outdated status "later"',
    "THREAD_3: missing follow-up PR",
  ]);
});

test("collectThreadInventoryIssues rejects duplicate thread IDs and original thread URLs", () => {
  const issues = collectThreadInventoryIssues([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "disposition",
      followUpPr: null,
      rationale: "First inventory entry.",
      content: "Reviewer requested a clarification.",
      outdated: false,
    },
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/other.py:22",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Second entry accidentally copied the first thread metadata.",
      content: "Reviewer requested a follow-up patch.",
      outdated: true,
    },
  ]);

  assert.deepEqual(issues, [
    "THREAD_1: duplicate thread ID also used by Thread 1",
    "THREAD_1: duplicate original thread URL also used by Thread 1",
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

test("normalizeOutdatedFieldValue parses yes/no values and preserves invalid input for validation", () => {
  assert.equal(normalizeOutdatedFieldValue("yes"), true);
  assert.equal(normalizeOutdatedFieldValue("no"), false);
  assert.equal(normalizeOutdatedFieldValue("later"), "later");
  assert.equal(normalizeOutdatedFieldValue("TBD"), null);
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
      outdated: false,
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

test("getCliConfiguration parses completeness validation, doc path, and output format", () => {
  assert.deepEqual(
    getCliConfiguration(["docs/custom.md", "--require-complete", "--exclude-outdated", "--format", "json"]),
    {
      docPath: path.resolve("docs/custom.md"),
      excludeOutdated: true,
      outputFormat: "json",
      requireComplete: true,
    }
  );
});

test("getCliConfiguration accepts markdown output", () => {
  assert.deepEqual(getCliConfiguration(["--format", "markdown"]), {
    docPath: DEFAULT_DOC_PATH,
    excludeOutdated: false,
    outputFormat: "markdown",
    requireComplete: false,
  });
});

test("getCliConfiguration rejects unknown options and extra positional arguments", () => {
  assert.throws(() => getCliConfiguration(["--unknown"]), /Unknown option: --unknown/);
  assert.throws(
    () => getCliConfiguration(["--format", "html"]),
    /Output format must be one of "text", "json", or "markdown"/
  );
  assert.throws(
    () => getCliConfiguration(["docs/one.md", "docs/two.md"]),
    /Unexpected argument: docs\/two\.md/
  );
});

test("the checked-in PR #178 inventory is still incomplete until real threads are recorded", () => {
  const threads = loadThreadInventory(DEFAULT_DOC_PATH);
  const issues = collectThreadInventoryIssues(threads);

  assert.equal(issues.length, 28);
  assert.match(formatThreadInventoryIssues(issues), /Thread inventory issues: 28/);
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
- Outdated: no
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
- Outdated: no
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
- Outdated: no
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
- Outdated:
`,
        }
      ),
    /Thread inventory issues: 7/
  );
});

test("buildFixThreadsReport can exclude outdated fix-classified threads from the branch scope", () => {
  const report = buildFixThreadsReport(
    {
      docPath: "docs/mixed.md",
      excludeOutdated: true,
      outputFormat: "json",
      requireComplete: true,
    },
    {
      readFileSync: () => `
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/582
- Rationale: The old implementation already moved, so this is no longer actionable.
- Content: Reviewer requested a patch on outdated code.
- Outdated: yes
`,
    }
  );

  const parsed = JSON.parse(report);
  assert.equal(parsed.count, 1);
  assert.equal(parsed.excludedOutdatedCount, 1);
  assert.equal(parsed.fixThreads[0].threadId, "THREAD_1");
});
