import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildInventoryVerificationReport,
  collectInventoryVerificationIssues,
  formatInventoryVerificationReport,
  getVerifierConfiguration,
} = require(path.join(repoRoot, "scripts/verify_pr_thread_inventory.js"));
const {
  parseThreadInventory,
} = require(path.join(repoRoot, "scripts/list_fix_threads_from_doc.js"));
const {
  extractThreadsFromSnapshot,
  extractUnresolvedThreads,
} = require(path.join(repoRoot, "scripts/list_unresolved_pr_threads.js"));

test("getVerifierConfiguration parses doc path and expected documented thread count", () => {
  const configuration = getVerifierConfiguration(
    [
      "octo/repo",
      "178",
      "--input",
      "threads.json",
      "--doc",
      "docs/custom.md",
      "--expect-doc-count",
      "4",
      "--expect-count",
      "0",
    ],
    {}
  );

  assert.equal(configuration.docPath, path.resolve("docs/custom.md"));
  assert.equal(configuration.expectDocCount, 4);
  assert.equal(configuration.expectedCount, 0);
});

test("collectInventoryVerificationIssues reports doc completeness and snapshot mismatches", () => {
  const documentedThreads = parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Code update is required.
- Content: Reviewer requested a fix.

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:22
- Classification: disposition
- Follow-up PR:
- Rationale: Existing behavior is intentional.
- Content: Reviewer requested an out-of-scope change.
`);
  const unresolvedThreads = [
    {
      id: "THREAD_1",
      comments: [],
    },
    {
      id: "THREAD_3",
      comments: [],
    },
  ];

  assert.deepEqual(
    collectInventoryVerificationIssues(documentedThreads, unresolvedThreads, {
      expectDocCount: 4,
    }),
    [
      "Expected 4 documented thread(s), found 2.",
      "Unresolved thread THREAD_3 is missing from the inventory document.",
      "Documented thread THREAD_2 is not unresolved in the provided snapshot.",
    ]
  );
});

test("formatInventoryVerificationReport summarizes passing verification", () => {
  const report = formatInventoryVerificationReport(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 4,
      expectedCount: 4,
    },
    [{ threadId: "THREAD_1" }],
    [{ id: "THREAD_1" }],
    []
  );

  assert.match(report, /Documented threads: 1/);
  assert.match(report, /Unresolved threads in snapshot: 1/);
  assert.match(report, /Expected documented threads: 4/);
  assert.match(report, /Expected unresolved threads: 4/);
  assert.match(report, /Verification: OK/);
});

test("buildInventoryVerificationReport accepts a complete matching document and snapshot", () => {
  const snapshotPath = path.join(
    repoRoot,
    "tests/fixtures/scripts/review_threads_snapshot.json"
  );
  const unresolvedThreads = extractUnresolvedThreads(
    extractThreadsFromSnapshot(
      require(path.join(repoRoot, "tests/fixtures/scripts/review_threads_snapshot.json"))
    )
  );
  const markdown = `
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: ${unresolvedThreads[0].id}
- Original Thread URL: ${unresolvedThreads[0].originalThreadUrl}
- Location: ${unresolvedThreads[0].path}:${unresolvedThreads[0].line}
- Classification: disposition
- Follow-up PR:
- Rationale: Reviewed and left as-is for fixture validation.
- Content: reviewer-a: Please keep this branch explicit.

### Thread 2

- Thread ID: ${unresolvedThreads[1].id}
- Original Thread URL: ${unresolvedThreads[1].originalThreadUrl}
- Location: ${unresolvedThreads[1].path}:${unresolvedThreads[1].line}
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Fixture thread stands in for a code-fix follow-up.
- Content: reviewer-b: Can this use fixture input too?
`;

  const passingReport = buildInventoryVerificationReport({
    owner: "stranske",
    repo: "trip-planner",
    prNumber: 178,
    inputPath: snapshotPath,
    docPath: path.resolve("docs/fixture-thread-inventory.md"),
    expectDocCount: 2,
    expectedCount: 2,
    token: undefined,
  }, {
    loadThreadInventory: () => parseThreadInventory(markdown),
  });

  assert.match(passingReport, /Verification: OK/);
});

test("buildInventoryVerificationReport includes unresolved count mismatches in the failure output", () => {
  const report = buildInventoryVerificationReport(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      token: undefined,
    },
    {
      loadThreadInventory: () =>
        parseThreadInventory(`
# PR #178 Unresolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Follow-up PR:
- Rationale: Inventory is complete.
- Content: Reviewer note.
`),
      loadReviewThreadsFromFile: () => [
        {
          id: "THREAD_1",
          isResolved: false,
          path: "trip_planner/example.py",
          line: 17,
          comments: {
            nodes: [],
          },
        },
      ],
    }
  );

  assert.match(report, /Verification: FAILED/);
  assert.match(report, /Expected 0 unresolved review thread\(s\), found 1\./);
});
