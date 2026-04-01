import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  extractUnresolvedThreads,
  formatUnresolvedThreadsReport,
  getConfiguration,
  normalizeBody,
} = require(path.join(repoRoot, "scripts/list_unresolved_pr_threads.js"));

test("getConfiguration applies defaults and parses explicit repository/PR inputs", () => {
  const configuration = getConfiguration(
    ["octo/repo", "42"],
    { GITHUB_TOKEN: "token-value" }
  );

  assert.deepEqual(configuration, {
    owner: "octo",
    repo: "repo",
    prNumber: 42,
    token: "token-value",
  });

  const defaults = getConfiguration([], { GITHUB_TOKEN: "token-value" });
  assert.equal(`${defaults.owner}/${defaults.repo}`, DEFAULT_REPOSITORY);
  assert.equal(defaults.prNumber, DEFAULT_PR_NUMBER);
});

test("extractUnresolvedThreads keeps unresolved threads and normalizes comment text", () => {
  const unresolved = extractUnresolvedThreads([
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
            body: "First line.\n\nSecond line.",
            createdAt: "2025-01-01T00:00:00Z",
            author: { login: "reviewer" },
          },
        ],
      },
    },
    {
      id: "THREAD_2",
      isResolved: true,
      isOutdated: false,
      path: "trip_planner/ignore.py",
      line: 5,
      comments: { nodes: [] },
    },
  ]);

  assert.deepEqual(unresolved, [
    {
      id: "THREAD_1",
      isOutdated: false,
      path: "trip_planner/example.py",
      line: 17,
      comments: [
        {
          id: "COMMENT_1",
          author: "reviewer",
          body: "First line. Second line.",
          createdAt: "2025-01-01T00:00:00Z",
        },
      ],
    },
  ]);

  assert.equal(normalizeBody(" one \n two  "), "one two");
});

test("formatUnresolvedThreadsReport renders thread identifiers and content", () => {
  const report = formatUnresolvedThreadsReport("stranske/trip-planner", 178, [
    {
      id: "THREAD_1",
      isOutdated: true,
      path: "scripts/list_unresolved_pr_threads.js",
      line: 99,
      comments: [
        {
          id: "COMMENT_1",
          author: "reviewer",
          body: "Please handle pagination.",
          createdAt: "2025-01-01T00:00:00Z",
        },
      ],
    },
  ]);

  assert.match(report, /Repository: stranske\/trip-planner/);
  assert.match(report, /Pull request: #178/);
  assert.match(report, /Unresolved review threads: 1/);
  assert.match(report, /1\. THREAD_1 \(scripts\/list_unresolved_pr_threads\.js:99, outdated\)/);
  assert.match(report, /reviewer: Please handle pagination\./);
});
