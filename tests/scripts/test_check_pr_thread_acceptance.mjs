import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_DOC_PATH,
  evaluateAcceptance,
  formatAcceptanceReport,
  getAcceptanceConfiguration,
} = require(path.join(repoRoot, "scripts/check_pr_thread_acceptance.js"));

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
  assert.equal(result.criteria[0].status, "pass");
  assert.equal(result.criteria[1].status, "pass");
  assert.equal(result.criteria[2].status, "blocked");
  assert.equal(result.criteria[3].status, "manual");
});

test("evaluateAcceptance passes repo-local verification when the inventory and snapshot match zero unresolved threads", async () => {
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
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          rationale: "The follow-up PR landed and the thread is resolved.",
          content: "reviewer: Please rework this helper.",
          outdated: false,
        },
      ],
      loadReviewThreadsFromFile: () => [],
    }
  );

  assert.equal(result.overallStatus, "blocked");
  assert.equal(result.unresolvedThreadCount, 0);
  assert.equal(result.criteria[0].status, "pass");
  assert.equal(result.criteria[1].status, "pass");
  assert.equal(result.criteria[2].status, "pass");
  assert.equal(result.criteria[3].status, "manual");
});

test("evaluateAcceptance passes when snapshot verification succeeds and GitHub UI confirmation is supplied", async () => {
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
      loadThreadInventory: () => [
        {
          threadId: "THREAD_1",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
          location: "trip_planner/example.py:17",
          classification: "fix",
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          rationale: "The follow-up PR landed and the thread is resolved.",
          content: "reviewer: Please rework this helper.",
          outdated: false,
        },
      ],
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
  assert.match(report, /- \[FAIL\] Criterion one: First failure/);
  assert.match(report, /  - Missing metadata/);
});
