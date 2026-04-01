import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  extractUnresolvedThreads,
  extractThreadsFromSnapshot,
  formatOutput,
  formatUnresolvedThreadsAsJson,
  formatUnresolvedThreadsAsMarkdown,
  formatUnresolvedThreadsReport,
  getConfiguration,
  loadReviewThreadsFromFile,
  normalizeBody,
  parseCommandLineArguments,
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
    inputPath: null,
    outputFormat: "text",
  });

  const defaults = getConfiguration([], { GITHUB_TOKEN: "token-value" });
  assert.equal(`${defaults.owner}/${defaults.repo}`, DEFAULT_REPOSITORY);
  assert.equal(defaults.prNumber, DEFAULT_PR_NUMBER);
});

test("getConfiguration accepts --input without requiring a GitHub token", () => {
  const configuration = getConfiguration(
    ["octo/repo", "178", "--input", "tests/fixtures/scripts/review_threads_snapshot.json"],
    {}
  );

  assert.equal(configuration.inputPath, "tests/fixtures/scripts/review_threads_snapshot.json");
  assert.equal(configuration.token, undefined);
  assert.equal(configuration.outputFormat, "text");
});

test("getConfiguration accepts structured output formats", () => {
  const configuration = getConfiguration(
    ["octo/repo", "178", "--input", "threads.json", "--format", "markdown"],
    {}
  );

  assert.equal(configuration.outputFormat, "markdown");
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

test("parseCommandLineArguments separates positional values from the --input flag", () => {
  assert.deepEqual(
    parseCommandLineArguments(["octo/repo", "178", "--input", "threads.json"]),
    {
      inputPath: "threads.json",
      outputFormat: "text",
      positional: ["octo/repo", "178"],
    }
  );
});

test("parseCommandLineArguments accepts an explicit output format", () => {
  assert.deepEqual(
    parseCommandLineArguments(["octo/repo", "178", "--input", "threads.json", "--format", "json"]),
    {
      inputPath: "threads.json",
      outputFormat: "json",
      positional: ["octo/repo", "178"],
    }
  );
});

test("loadReviewThreadsFromFile supports GraphQL snapshot payloads", () => {
  const snapshotPath = path.join(
    repoRoot,
    "tests/fixtures/scripts/review_threads_snapshot.json"
  );

  const threads = loadReviewThreadsFromFile(snapshotPath);

  assert.equal(threads.length, 3);
  assert.equal(threads[0].id, "THREAD_A");
  assert.equal(threads[2].id, "THREAD_C");
});

test("extractThreadsFromSnapshot rejects unsupported snapshot shapes", () => {
  assert.throws(
    () => extractThreadsFromSnapshot({ data: { repository: {} } }),
    /supported thread collection/
  );
});

test("snapshot fixtures can drive the unresolved thread report offline", () => {
  const snapshotPath = path.join(
    repoRoot,
    "tests/fixtures/scripts/review_threads_snapshot.json"
  );
  const snapshot = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
  const unresolvedThreads = extractUnresolvedThreads(extractThreadsFromSnapshot(snapshot));
  const report = formatUnresolvedThreadsReport("stranske/trip-planner", 178, unresolvedThreads);

  assert.match(report, /Unresolved review threads: 2/);
  assert.match(report, /THREAD_A \(trip_planner\/example\.py:17\)/);
  assert.match(report, /THREAD_C \(scripts\/list_unresolved_pr_threads\.js:121, outdated\)/);
  assert.match(report, /reviewer-b: Can this use fixture input too\?/);
});

test("formatUnresolvedThreadsAsJson emits machine-readable unresolved thread data", () => {
  const report = formatUnresolvedThreadsAsJson("stranske/trip-planner", 178, [
    {
      id: "THREAD_1",
      isOutdated: false,
      path: "scripts/list_unresolved_pr_threads.js",
      line: 99,
      comments: [],
    },
  ]);

  const parsed = JSON.parse(report);
  assert.equal(parsed.repository, "stranske/trip-planner");
  assert.equal(parsed.prNumber, 178);
  assert.equal(parsed.unresolvedThreads[0].id, "THREAD_1");
});

test("formatUnresolvedThreadsAsMarkdown emits a doc-ready inventory skeleton", () => {
  const report = formatUnresolvedThreadsAsMarkdown("stranske/trip-planner", 178, [
    {
      id: "THREAD_1",
      isOutdated: true,
      path: "scripts/list_unresolved_pr_threads.js",
      line: 99,
      comments: [
        {
          author: "reviewer",
          body: "Please handle pagination.",
        },
      ],
    },
  ]);

  assert.match(report, /# stranske\/trip-planner PR #178 Unresolved Threads/);
  assert.match(report, /- Thread ID: THREAD_1/);
  assert.match(report, /- Location: scripts\/list_unresolved_pr_threads\.js:99/);
  assert.match(report, /- Classification:/);
  assert.match(report, /- Rationale:/);
  assert.match(report, /- reviewer: Please handle pagination\./);
});

test("formatOutput dispatches to the requested formatter", () => {
  const unresolvedThreads = [
    {
      id: "THREAD_1",
      isOutdated: false,
      path: "scripts/list_unresolved_pr_threads.js",
      line: 99,
      comments: [],
    },
  ];

  assert.match(formatOutput("stranske/trip-planner", 178, unresolvedThreads, "text"), /THREAD_1/);
  assert.doesNotThrow(() =>
    JSON.parse(formatOutput("stranske/trip-planner", 178, unresolvedThreads, "json"))
  );
  assert.match(
    formatOutput("stranske/trip-planner", 178, unresolvedThreads, "markdown"),
    /## Thread 1/
  );
});
