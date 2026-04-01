import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildPullRequestPayload,
  buildSuggestedBranchName,
  buildFixThreadsReport,
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  extractPullRequestNumber,
  formatFixThreadsAsJson,
  formatFixThreadsAsPlan,
  formatFixThreadsAsMarkdown,
  formatFixThreadsAsPullRequestPayloads,
  formatFixThreadsOutput,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  groupFixThreadsByFollowUpPr,
  isPlaceholderValue,
  listActionableFixThreads,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeOutdatedFieldValue,
  normalizeFollowUpPrFieldValue,
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

test("parseThreadInventory canonicalizes follow-up PR number shorthand", () => {
  const threads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: PR #581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: fix
- Follow-up PR: pull/582
- Rationale: Secondary code path needs the same patch.
- Content: Reviewer requested parity with the primary branch.
- Outdated: no
`);

  assert.deepEqual(
    threads.map((thread) => thread.followUpPr),
    [
      "https://github.com/stranske/trip-planner/pull/581",
      "https://github.com/stranske/trip-planner/pull/582",
    ]
  );
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

test("parseThreadInventory can isolate unresolved and resolved inventory sections", () => {
  const markdown = `
# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_ACTIVE
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Rationale: Still unresolved.
- Content: Reviewer requested a clarification.
- Outdated: no

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_RESOLVED
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Historical fix triage should stay archived.
- Content: Reviewer requested a follow-up patch.
- Outdated: yes
`;

  assert.deepEqual(parseThreadInventory(markdown, { inventorySection: "unresolved" }), [
    {
      threadId: "THREAD_ACTIVE",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "disposition",
      followUpPr: null,
      rationale: "Still unresolved.",
      content: "Reviewer requested a clarification.",
      outdated: false,
    },
  ]);
  assert.deepEqual(parseThreadInventory(markdown, { inventorySection: "resolved" }), [
    {
      threadId: "THREAD_RESOLVED",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:8",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Historical fix triage should stay archived.",
      content: "Reviewer requested a follow-up patch.",
      outdated: true,
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

test("groupFixThreadsByFollowUpPr preserves bounded follow-up PR scope", () => {
  const groups = groupFixThreadsByFollowUpPr([
    {
      threadId: "THREAD_1",
      location: "trip_planner/example.py:17",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
    },
    {
      threadId: "THREAD_2",
      location: "trip_planner/other.py:8",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
    },
    {
      threadId: "THREAD_3",
      location: "trip_planner/third.py:4",
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
    },
  ]);

  assert.deepEqual(groups, [
    {
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      threadCount: 2,
      threads: [
        {
          threadId: "THREAD_1",
          location: "trip_planner/example.py:17",
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          suggestedBranch: "pr-178-fix/trip-planner-example-py-17-thread-1",
        },
        {
          threadId: "THREAD_2",
          location: "trip_planner/other.py:8",
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          suggestedBranch: "pr-178-fix/trip-planner-other-py-8-thread-2",
        },
      ],
    },
    {
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
      threadCount: 1,
      threads: [
        {
          threadId: "THREAD_3",
          location: "trip_planner/third.py:4",
          followUpPr: "https://github.com/stranske/trip-planner/pull/582",
          suggestedBranch: "pr-178-fix/trip-planner-third-py-4-thread-3",
        },
      ],
    },
  ]);
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
  assert.match(report, /Follow-up PR groups: 1/);
  assert.match(
    report,
    /1\. https:\/\/github\.com\/stranske\/trip-planner\/pull\/581 \(1 thread\)/
  );
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
  assert.equal(parsed.followUpPrGroups.length, 1);
  assert.equal(
    parsed.followUpPrGroups[0].threads[0].suggestedBranch,
    "pr-178-fix/trip-planner-example-py-17-thread-1"
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
  assert.match(report, /## Follow-up PR Groups/);
  assert.match(
    report,
    /### Follow-up PR Group 1: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(report, /- Thread Count: 1/);
  assert.match(
    report,
    /- \[ \] THREAD_1 via `pr-178-fix\/trip-planner-example-py-17-thread-1`/
  );
});

test("formatFixThreadsAsMarkdown reports excluded outdated fix threads", () => {
  const report = formatFixThreadsAsMarkdown([], { excludedOutdatedCount: 1 });

  assert.match(report, /Excluded outdated fix threads: 1/);
  assert.match(report, /No fix-classified threads found\./);
});

test("formatFixThreadsAsPlan emits a bounded follow-up PR execution plan", () => {
  const report = formatFixThreadsAsPlan([
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
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Separate code path needs the same guard.",
      content: "Reviewer requested parity with the primary branch.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Follow-up PR Execution Plan/);
  assert.match(report, /Actionable fix threads: 2/);
  assert.match(report, /Follow-up PR groups: 1/);
  assert.match(
    report,
    /## Follow-up PR Group 1: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(report, /- Thread Count: 2/);
  assert.match(report, /- Thread: THREAD_1/);
  assert.match(report, /- Suggested Branch: `pr-178-fix\/trip-planner-example-py-17-thread-1`/);
  assert.match(
    report,
    /- Next Step: Implement the requested code change and reply on the follow-up PR\./
  );
});

test("extractPullRequestNumber reads the numeric suffix from a follow-up PR URL", () => {
  assert.equal(
    extractPullRequestNumber("https://github.com/stranske/trip-planner/pull/581"),
    "581"
  );
  assert.equal(extractPullRequestNumber(null), null);
  assert.equal(extractPullRequestNumber("https://example.com/not-a-pr"), null);
});

test("buildPullRequestPayload creates a PR-ready title and body for a bounded thread group", () => {
  const payload = buildPullRequestPayload(
    {
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      threadCount: 2,
      threads: [
        {
          threadId: "THREAD_1",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
          location: "trip_planner/example.py:17",
          rationale: "Code path still drops the final stop.",
          content: "Reviewer requested a bounds check.",
        },
        {
          threadId: "THREAD_2",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
          location: "trip_planner/other.py:8",
          rationale: "Separate code path needs the same guard.",
          content: "Reviewer requested parity with the primary branch.",
        },
      ],
    },
    0
  );

  assert.equal(payload.followUpPrNumber, "581");
  assert.equal(payload.title, "Address PR #178 fix threads for follow-up PR #581");
  assert.match(payload.body, /## Summary/);
  assert.match(payload.body, /Address 2 fix-classified review threads carried from PR #178\./);
  assert.match(payload.body, /## Original Review Threads/);
  assert.match(payload.body, /- THREAD_1 \(trip_planner\/example\.py:17\)/);
  assert.match(
    payload.body,
    /- Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/
  );
  assert.match(payload.body, /- Requested Change: Reviewer requested a bounds check\./);
  assert.match(payload.body, /## Validation/);
});

test("formatFixThreadsAsPullRequestPayloads renders each follow-up PR group as a reusable payload", () => {
  const report = formatFixThreadsAsPullRequestPayloads([
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
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
      rationale: "Secondary code path needs the same patch.",
      content: "Reviewer requested parity with the primary branch.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Follow-up PR Payloads/);
  assert.match(
    report,
    /## Follow-up PR Group 1: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(report, /Title: Address PR #178 fix threads for follow-up PR #581/);
  assert.match(report, /```markdown/);
  assert.match(report, /## Original Review Threads/);
  assert.match(
    report,
    /## Follow-up PR Group 2: https:\/\/github\.com\/stranske\/trip-planner\/pull\/582/
  );
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
  assert.match(formatFixThreadsOutput(fixThreads, "plan"), /# Follow-up PR Execution Plan/);
  assert.match(
    formatFixThreadsOutput(fixThreads, "pr-payload"),
    /# Follow-up PR Payloads/
  );
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

test("normalizeFollowUpPrFieldValue canonicalizes PR number shorthand", () => {
  assert.equal(
    normalizeFollowUpPrFieldValue("#581"),
    "https://github.com/stranske/trip-planner/pull/581"
  );
  assert.equal(
    normalizeFollowUpPrFieldValue("PR #582"),
    "https://github.com/stranske/trip-planner/pull/582"
  );
  assert.equal(
    normalizeFollowUpPrFieldValue("pull/583"),
    "https://github.com/stranske/trip-planner/pull/583"
  );
  assert.equal(
    normalizeFollowUpPrFieldValue("https://github.com/stranske/trip-planner/pull/584"),
    "https://github.com/stranske/trip-planner/pull/584"
  );
  assert.equal(normalizeFollowUpPrFieldValue("TBD"), null);
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
    getCliConfiguration([
      "docs/custom.md",
      "--require-complete",
      "--exclude-outdated",
      "--follow-up-pr",
      "#581",
      "--format",
      "json",
    ]),
    {
      docPath: path.resolve("docs/custom.md"),
      excludeOutdated: true,
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      outputFormat: "json",
      requireComplete: true,
    }
  );
});

test("getCliConfiguration accepts markdown output", () => {
  assert.deepEqual(getCliConfiguration(["--format", "markdown"]), {
    docPath: DEFAULT_DOC_PATH,
    excludeOutdated: false,
    followUpPr: null,
    outputFormat: "markdown",
    requireComplete: false,
  });
});

test("getCliConfiguration accepts plan output", () => {
  assert.deepEqual(getCliConfiguration(["--format", "plan"]), {
    docPath: DEFAULT_DOC_PATH,
    excludeOutdated: false,
    followUpPr: null,
    outputFormat: "plan",
    requireComplete: false,
  });
});

test("getCliConfiguration rejects unknown options and extra positional arguments", () => {
  assert.throws(() => getCliConfiguration(["--unknown"]), /Unknown option: --unknown/);
  assert.throws(
    () => getCliConfiguration(["--follow-up-pr"]),
    /The --follow-up-pr flag requires a value\./
  );
  assert.throws(
    () => getCliConfiguration(["--follow-up-pr", "TBD"]),
    /The --follow-up-pr flag requires a non-placeholder URL/
  );
  assert.throws(
    () => getCliConfiguration(["--format", "html"]),
    /Output format must be one of "text", "json", "markdown", "plan", or "pr-payload"/
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

test("buildFixThreadsReport can isolate a single bounded follow-up PR scope", () => {
  const report = buildFixThreadsReport(
    {
      docPath: "docs/mixed.md",
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
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
- Rationale: Separate code path needs the same guard.
- Content: Reviewer requested parity with the primary branch.
- Outdated: no
`,
    }
  );

  const parsed = JSON.parse(report);
  assert.equal(parsed.count, 1);
  assert.equal(parsed.fixThreads[0].threadId, "THREAD_2");
  assert.equal(parsed.followUpPrGroups.length, 1);
  assert.equal(parsed.followUpPrGroups[0].followUpPr, "https://github.com/stranske/trip-planner/pull/582");
});

test("buildFixThreadsReport matches follow-up PR shorthand against canonicalized inventory values", () => {
  const report = buildFixThreadsReport(
    {
      docPath: "docs/mixed.md",
      followUpPr: "PR #582",
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
- Follow-up PR: #581
- Rationale: Code path still drops the final stop.
- Content: Reviewer requested a bounds check.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:8
- Classification: fix
- Follow-up PR: pull/582
- Rationale: Separate code path needs the same guard.
- Content: Reviewer requested parity with the primary branch.
- Outdated: no
`,
    }
  );

  const parsed = JSON.parse(report);
  assert.equal(parsed.count, 1);
  assert.equal(parsed.fixThreads[0].threadId, "THREAD_2");
  assert.equal(parsed.followUpPrGroups[0].followUpPr, "https://github.com/stranske/trip-planner/pull/582");
});

test("buildFixThreadsReport excludes resolved-history fix threads from active follow-up scope", () => {
  const report = buildFixThreadsReport(
    {
      docPath: "docs/resolved-only.md",
      outputFormat: "json",
      requireComplete: true,
    },
    {
      readFileSync: () => `
# PR #178 Unresolved Thread Inventory

## Thread Inventory

No unresolved inline review threads found.

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: The fix landed and the review thread is now historical only.
- Content: Reviewer requested a bounds check.
- Outdated: no
`,
    }
  );

  const parsed = JSON.parse(report);
  assert.equal(parsed.count, 0);
  assert.equal(parsed.followUpPrGroups.length, 0);
});
