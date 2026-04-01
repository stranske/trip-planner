import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_DOC_PATH,
  evaluateAcceptance,
  formatAcceptanceReport,
  formatVerificationMode,
  getAcceptanceConfiguration,
  loadResolutionResultsReport,
} = require(path.join(repoRoot, "scripts/check_pr_thread_acceptance.js"));
const {
  parseThreadInventory,
} = require(path.join(repoRoot, "scripts/list_fix_threads_from_doc.js"));

test("getAcceptanceConfiguration parses acceptance-specific options", () => {
  const configuration = getAcceptanceConfiguration(
    [
      "octo/repo",
      "178",
      "--input",
      "threads.json",
      "--doc",
      "docs/custom.md",
      "--expect-doc-count",
      "6",
      "--expect-count",
      "0",
      "--github-ui-confirmed",
      "--format",
      "json",
    ],
    {}
  );

  assert.equal(configuration.owner, "octo");
  assert.equal(configuration.repo, "repo");
  assert.equal(configuration.prNumber, 178);
  assert.equal(configuration.inputPath, "threads.json");
  assert.equal(configuration.docPath, path.resolve("docs/custom.md"));
  assert.equal(configuration.expectDocCount, 6);
  assert.equal(configuration.expectedCount, 0);
  assert.equal(configuration.githubUiConfirmed, true);
  assert.equal(configuration.outputFormat, "json");
  assert.equal(configuration.writeInventoryDoc, false);
});

test("getAcceptanceConfiguration accepts --write-inventory-doc", () => {
  const configuration = getAcceptanceConfiguration(
    ["octo/repo", "178", "--input", "threads.json", "--write-inventory-doc"],
    {}
  );

  assert.equal(configuration.writeInventoryDoc, true);
});

test("loadResolutionResultsReport derives reusable verification defaults from a resolution report", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-report-"));
  const resultsPath = path.join(tempDir, "results.json");

  fs.writeFileSync(
    resultsPath,
    `${JSON.stringify(
      {
        remainingSnapshotPath: path.join(tempDir, "remaining.json"),
        inventoryUpdate: {
          docPath: path.join(tempDir, "pr-178-unresolved-threads.md"),
        },
        acceptance: {
          repository: "stranske/trip-planner",
          prNumber: 178,
          expectDocCount: 4,
          expectedCount: 0,
          docPath: path.join(tempDir, "fallback-doc.md"),
          inputPath: "<post-resolution inventory>",
          criteria: [{ id: "github_ui", status: "pass" }],
        },
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  assert.deepEqual(loadResolutionResultsReport(resultsPath), {
    repository: "stranske/trip-planner",
    prNumber: "178",
    docPath: path.join(tempDir, "pr-178-unresolved-threads.md"),
    expectDocCount: 4,
    expectedCount: 0,
    inputPath: path.join(tempDir, "remaining.json"),
    snapshotThreads: null,
    githubUiConfirmed: true,
  });
});

test("loadResolutionResultsReport reuses embedded snapshot threads when no snapshot file was written", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-embedded-"));
  const resultsPath = path.join(tempDir, "results.json");
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const remainingThreadsSnapshot = [
    {
      id: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      path: "src/file.js",
      line: 12,
      isOutdated: false,
      comments: [{ id: "COMMENT_2", author: "reviewer", body: "Keep this open." }],
    },
  ];

  fs.writeFileSync(
    resultsPath,
    `${JSON.stringify(
      {
        inventoryUpdate: { docPath },
        remainingThreadsSnapshot,
        acceptance: {
          repository: "stranske/trip-planner",
          prNumber: 178,
          expectDocCount: 4,
          expectedCount: 1,
          inputPath: "<post-resolution inventory>",
          criteria: [{ id: "github_ui", status: "manual" }],
        },
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  assert.deepEqual(loadResolutionResultsReport(resultsPath), {
    repository: "stranske/trip-planner",
    prNumber: "178",
    docPath,
    expectDocCount: 4,
    expectedCount: 1,
    inputPath: null,
    snapshotThreads: remainingThreadsSnapshot,
    githubUiConfirmed: false,
  });
});

test("getAcceptanceConfiguration can reuse a persisted resolution report", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-config-"));
  const resultsPath = path.join(tempDir, "results.json");
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const snapshotPath = path.join(tempDir, "remaining.json");

  fs.writeFileSync(
    resultsPath,
    `${JSON.stringify(
      {
        remainingSnapshotPath: snapshotPath,
        inventoryUpdate: { docPath },
        acceptance: {
          repository: "stranske/trip-planner",
          prNumber: 178,
          expectDocCount: 4,
          expectedCount: 0,
          criteria: [{ id: "github_ui", status: "manual" }],
        },
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  const configuration = getAcceptanceConfiguration(["--results", resultsPath], {});

  assert.equal(configuration.owner, "stranske");
  assert.equal(configuration.repo, "trip-planner");
  assert.equal(configuration.prNumber, 178);
  assert.equal(configuration.inputPath, snapshotPath);
  assert.equal(configuration.snapshotThreads, null);
  assert.equal(configuration.docPath, docPath);
  assert.equal(configuration.expectDocCount, 4);
  assert.equal(configuration.expectedCount, 0);
  assert.equal(configuration.githubUiConfirmed, false);
  assert.equal(configuration.resultsPath, resultsPath);
});

test("getAcceptanceConfiguration lets explicit CLI overrides win over a persisted resolution report", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-cli-overrides-"));
  const resultsPath = path.join(tempDir, "results.json");
  const reportDocPath = path.join(tempDir, "report-doc.md");
  const overrideDocPath = path.join(tempDir, "override-doc.md");
  const snapshotPath = path.join(tempDir, "remaining.json");

  fs.writeFileSync(
    resultsPath,
    `${JSON.stringify(
      {
        remainingSnapshotPath: snapshotPath,
        inventoryUpdate: { docPath: reportDocPath },
        acceptance: {
          repository: "stranske/trip-planner",
          prNumber: 178,
          expectDocCount: 4,
          expectedCount: 0,
          criteria: [{ id: "github_ui", status: "manual" }],
        },
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  const configuration = getAcceptanceConfiguration(
    [
      "--results",
      resultsPath,
      "--doc",
      overrideDocPath,
      "--expect-doc-count",
      "2",
      "--expect-count",
      "1",
    ],
    {}
  );

  assert.equal(configuration.docPath, path.resolve(overrideDocPath));
  assert.equal(configuration.expectDocCount, 2);
  assert.equal(configuration.expectedCount, 1);
  assert.equal(configuration.inputPath, snapshotPath);
});

test("getAcceptanceConfiguration reuses embedded snapshot threads from a persisted resolution report", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-config-embedded-"));
  const resultsPath = path.join(tempDir, "results.json");
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const snapshotThreads = [
    {
      id: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      path: "src/file.js",
      line: 12,
      isOutdated: false,
      comments: [
        {
          id: "COMMENT_2",
          author: "reviewer",
          body: "Keep this open.",
          url: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        },
      ],
    },
  ];

  fs.writeFileSync(
    resultsPath,
    `${JSON.stringify(
      {
        inventoryUpdate: { docPath },
        remainingThreadsSnapshot: snapshotThreads,
        acceptance: {
          repository: "stranske/trip-planner",
          prNumber: 178,
          expectDocCount: 4,
          expectedCount: 1,
          criteria: [{ id: "github_ui", status: "manual" }],
        },
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  const configuration = getAcceptanceConfiguration(["--results", resultsPath], {});

  assert.equal(configuration.inputPath, null);
  assert.deepEqual(configuration.snapshotThreads, snapshotThreads);
  assert.equal(configuration.docPath, docPath);
  assert.equal(configuration.expectedCount, 1);
});

test("loadResolutionResultsReport rejects invalid resolution report payloads", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "acceptance-results-invalid-"));
  const missingAcceptancePath = path.join(tempDir, "missing-acceptance.json");
  const malformedPath = path.join(tempDir, "malformed.json");

  fs.writeFileSync(missingAcceptancePath, `${JSON.stringify({ threadCount: 0 })}\n`, "utf8");
  fs.writeFileSync(malformedPath, "{not-json}\n", "utf8");

  assert.throws(
    () => loadResolutionResultsReport(missingAcceptancePath),
    /must contain an "acceptance" object/
  );
  assert.throws(
    () => loadResolutionResultsReport(malformedPath),
    /Could not parse results report/
  );
});

test("getAcceptanceConfiguration rejects ambiguous or incomplete live verification options", () => {
  assert.throws(
    () => getAcceptanceConfiguration(["octo/repo", "178", "--live"], {}),
    /GITHUB_TOKEN is required when --live is specified/
  );
  assert.throws(
    () =>
      getAcceptanceConfiguration(
        ["octo/repo", "178", "--live", "--input", "threads.json"],
        { GITHUB_TOKEN: "token-value" }
      ),
    /--live and --input options are mutually exclusive/
  );
});

test("evaluateAcceptance reports blocked snapshot verification when no token or snapshot is provided", async () => {
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: null,
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: () => [
        {
          threadId: "THREAD_1",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
          location: "trip_planner/example.py:17",
          classification: "disposition",
          followUpPr: null,
          rationale: "The requested change is intentionally out of scope.",
          content: "reviewer: Please rework this helper.",
          outdated: false,
        },
      ],
    }
  );

  assert.equal(result.overallStatus, "blocked");
  assert.equal(result.verificationMode, "none");
  assert.equal(result.criteria[0].status, "pass");
  assert.equal(result.criteria[1].status, "pass");
  assert.equal(result.criteria[2].status, "blocked");
  assert.equal(result.criteria[3].status, "manual");
});

test("evaluateAcceptance does not count blank thread templates as documented entries", async () => {
  const templateOnlyInventory = `
# PR #178 Unresolved Thread Inventory

## Status

The exact 4 unresolved threads for PR #178 are still not available in this environment.

## Thread Template

### Thread 1

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:

### Thread 2

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:
`;
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: null,
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 4,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) =>
        parseThreadInventory(templateOnlyInventory, options),
    }
  );

  assert.equal(result.overallStatus, "fail");
  assert.equal(result.documentedThreadCount, 0);
  assert.equal(result.criteria[0].status, "fail");
  assert.match(result.criteria[0].details, /Found 0 documented thread entries/);
  assert.deepEqual(result.criteria[0].issues, []);
});

test("evaluateAcceptance passes repo-local verification when the inventory and snapshot match zero unresolved threads", async () => {
  const resolvedOnlyInventory = `
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
- Rationale: The follow-up PR landed and the thread is resolved.
- Content: reviewer: Please rework this helper.
- Outdated: no
`;
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) =>
        parseThreadInventory(resolvedOnlyInventory, options),
      loadReviewThreadsFromFile: () => [],
    }
  );

  assert.equal(result.overallStatus, "manual");
  assert.equal(result.verificationMode, "snapshot");
  assert.equal(result.unresolvedThreadCount, 0);
  assert.equal(result.criteria[0].status, "pass");
  assert.equal(result.criteria[1].status, "pass");
  assert.equal(result.criteria[2].status, "pass");
  assert.equal(result.criteria[3].status, "manual");
  assert.match(result.criteria[3].details, /cannot verify the live GitHub UI state/i);
});

test("evaluateAcceptance can verify embedded snapshot threads from a persisted results report", async () => {
  const activeInventory = `
# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: src/file.js:12
- Classification: disposition
- Follow-up PR:
- Rationale: The disposition reply is still pending.
- Content: reviewer: Keep this open.
- Outdated: no
`;
  const snapshotThreads = [
    {
      id: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      path: "src/file.js",
      line: 12,
      isOutdated: false,
      comments: [
        {
          id: "COMMENT_2",
          author: "reviewer",
          body: "Keep this open.",
          url: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        },
      ],
    },
  ];

  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: null,
      snapshotThreads,
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 1,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) =>
        parseThreadInventory(activeInventory, options),
    }
  );

  assert.equal(result.verificationMode, "snapshot");
  assert.equal(result.inputPath, null);
  assert.deepEqual(result.snapshotThreads, snapshotThreads);
  assert.equal(result.unresolvedThreadCount, 1);
  assert.equal(result.criteria[2].status, "pass");
});

test("evaluateAcceptance can sync the inventory document before verifying a zero-thread snapshot", async () => {
  const resolvedOnlyInventory = `
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
- Rationale: The follow-up PR landed and the thread is resolved.
- Content: reviewer: Please rework this helper.
- Outdated: no
`;

  let writeInventoryDocumentCalls = 0;
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
      writeInventoryDoc: true,
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) =>
        parseThreadInventory(
          writeInventoryDocumentCalls === 0
            ? `
# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: The follow-up PR landed and the thread is resolved.
- Content: reviewer: Please rework this helper.
- Outdated: no
`
            : resolvedOnlyInventory,
          options
        ),
      loadReviewThreadsFromFile: () => [],
      writeInventoryDocument: () => {
        writeInventoryDocumentCalls += 1;
      },
    }
  );

  assert.equal(writeInventoryDocumentCalls, 1);
  assert.equal(result.inventoryDocumentUpdated, true);
  assert.equal(result.overallStatus, "manual");
  assert.equal(result.criteria[2].status, "pass");
});

test("evaluateAcceptance fails repo-local verification when zero unresolved threads are reported but the active inventory section still contains entries", async () => {
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) => {
        if (options.inventorySection === "unresolved") {
          return [
            {
              threadId: "THREAD_1",
              originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
              location: "trip_planner/example.py:17",
              classification: "fix",
              followUpPr: "https://github.com/stranske/trip-planner/pull/581",
              rationale: "The follow-up PR landed, but the inventory was not moved yet.",
              content: "reviewer: Please rework this helper.",
              outdated: false,
            },
          ];
        }

        return [
          {
            threadId: "THREAD_1",
            originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
            location: "trip_planner/example.py:17",
            classification: "fix",
            followUpPr: "https://github.com/stranske/trip-planner/pull/581",
            rationale: "The follow-up PR landed, but the inventory was not moved yet.",
            content: "reviewer: Please rework this helper.",
            outdated: false,
          },
        ];
      },
      loadReviewThreadsFromFile: () => [],
    }
  );

  assert.equal(result.overallStatus, "fail");
  assert.equal(result.unresolvedThreadCount, 0);
  assert.equal(result.criteria[2].status, "fail");
  assert.match(
    result.criteria[2].issues.join("\n"),
    /Documented unresolved inventory must be empty when the snapshot has zero unresolved thread\(s\); found 1 active thread entry\./
  );
});

test("evaluateAcceptance passes when snapshot verification succeeds and GitHub UI confirmation is supplied", async () => {
  const resolvedOnlyInventory = `
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
- Rationale: The follow-up PR landed and the thread is resolved.
- Content: reviewer: Please rework this helper.
- Outdated: no
`;
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: true,
      outputFormat: "text",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) =>
        parseThreadInventory(resolvedOnlyInventory, options),
      loadReviewThreadsFromFile: () => [],
    }
  );

  assert.equal(result.overallStatus, "pass");
  assert.equal(result.unresolvedThreadCount, 0);
  assert.equal(result.criteria[0].status, "pass");
  assert.equal(result.criteria[1].status, "pass");
  assert.equal(result.criteria[2].status, "pass");
  assert.equal(result.criteria[3].status, "pass");
  assert.match(result.criteria[3].details, /explicitly confirmed/);
});

test("evaluateAcceptance fails when fix threads are missing follow-up PR links or snapshot state diverges", async () => {
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: "threads.json",
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: () => [
        {
          threadId: "THREAD_1",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
          location: "trip_planner/example.py:17",
          classification: "fix",
          followUpPr: null,
          rationale: "Code changes are still required.",
          content: "reviewer: Please rework this helper.",
          outdated: false,
        },
      ],
      loadReviewThreadsFromFile: () => [
        {
          id: "THREAD_1",
          isResolved: false,
          isOutdated: false,
          path: "trip_planner/example.py",
          line: 17,
          comments: {
            nodes: [
              {
                id: "COMMENT_1",
                body: "Please rework this helper.",
                createdAt: "2025-01-01T00:00:00Z",
                url: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
                author: { login: "reviewer" },
              },
            ],
          },
        },
      ],
    }
  );

  assert.equal(result.overallStatus, "fail");
  assert.equal(result.criteria[1].status, "fail");
  assert.match(result.criteria[1].issues[0], /missing follow-up PR/);
  assert.equal(result.criteria[2].status, "fail");
  assert.match(result.criteria[2].issues.join("\n"), /Expected 0 unresolved review thread\(s\), found 1\./);
});

test("evaluateAcceptance fails when a fix thread uses a non-PR follow-up link", async () => {
  const result = await evaluateAcceptance(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: null,
      inputPath: null,
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      expectDocCount: 1,
      expectedCount: 0,
      githubUiConfirmed: false,
      outputFormat: "text",
    },
    {
      loadThreadInventory: () => [
        {
          threadId: "THREAD_1",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
          location: "trip_planner/example.py:17",
          classification: "fix",
          followUpPr: "https://github.com/stranske/trip-planner/issues/581",
          rationale: "Code changes were tracked, but the stored link points to an issue.",
          content: "reviewer: Please rework this helper.",
          outdated: false,
        },
      ],
    }
  );

  assert.equal(result.overallStatus, "fail");
  assert.equal(result.criteria[0].status, "fail");
  assert.match(result.criteria[0].issues[0], /invalid follow-up PR/);
  assert.equal(result.criteria[1].status, "fail");
  assert.match(result.criteria[1].issues[0], /invalid follow-up PR/);
});

test("formatAcceptanceReport renders criterion statuses and issue details", () => {
  const report = formatAcceptanceReport(
    {
      repository: "stranske/trip-planner",
      prNumber: 178,
      docPath: DEFAULT_DOC_PATH,
      verificationMode: "snapshot",
      inputPath: "threads.json",
      inventoryDocumentUpdated: true,
      overallStatus: "fail",
      criteria: [
        {
          label: "Criterion one",
          status: "fail",
          details: "First failure",
          issues: ["Missing metadata"],
        },
      ],
    }
  );

  assert.match(report, /Overall status: FAIL/);
  assert.match(report, /Review-thread verification: SNAPSHOT \(threads\.json\)/);
  assert.match(report, /Inventory document sync: UPDATED/);
  assert.match(report, /- \[FAIL\] Criterion one: First failure/);
  assert.match(report, /  - Missing metadata/);
});

test("formatAcceptanceReport renders manual overall status", () => {
  const report = formatAcceptanceReport(
    {
      repository: "stranske/trip-planner",
      prNumber: 178,
      docPath: DEFAULT_DOC_PATH,
      verificationMode: "none",
      inputPath: null,
      overallStatus: "manual",
      criteria: [
        {
          label: "GitHub UI shows no unresolved inline review threads",
          status: "manual",
          details: "Manual verification is still required.",
          issues: [],
        },
      ],
    }
  );

  assert.match(report, /Overall status: MANUAL/);
  assert.match(report, /Review-thread verification: NOT RUN/);
  assert.match(
    report,
    /- \[MANUAL\] GitHub UI shows no unresolved inline review threads: Manual verification is still required\./
  );
});

test("formatVerificationMode describes snapshot, live, and missing verification inputs", () => {
  assert.equal(
    formatVerificationMode({ verificationMode: "snapshot", inputPath: "tmp/threads.json" }),
    "SNAPSHOT (tmp/threads.json)"
  );
  assert.equal(
    formatVerificationMode({ verificationMode: "snapshot", inputPath: null }),
    "SNAPSHOT (embedded results report)"
  );
  assert.equal(formatVerificationMode({ verificationMode: "live", inputPath: null }), "LIVE API");
  assert.equal(formatVerificationMode({ verificationMode: "none", inputPath: null }), "NOT RUN");
});
