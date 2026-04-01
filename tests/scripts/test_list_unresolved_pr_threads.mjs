import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  buildMarkdownThreadSection,
  extractUnresolvedThreads,
  extractThreadsFromSnapshot,
  fetchAllReviewThreads,
  formatOutput,
  formatThreadContent,
  formatUnresolvedThreadsAsJson,
  formatUnresolvedThreadsAsMarkdown,
  formatUnresolvedThreadsReport,
  getConfiguration,
  loadReviewThreadsFromFile,
  mergeInventoryIntoDocument,
  normalizeBody,
  normalizeSnapshotThreadCollection,
  parseCommandLineArguments,
  validateExpectedCount,
  writeInventoryDocument,
} = require(path.join(repoRoot, "scripts/list_unresolved_pr_threads.js"));
const { parseThreadInventory } = require(path.join(repoRoot, "scripts/list_fix_threads_from_doc.js"));

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
    expectedCount: null,
    inventoryDocPath: null,
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
  assert.equal(configuration.expectedCount, null);
});

test("getConfiguration accepts structured output formats", () => {
  const configuration = getConfiguration(
    ["octo/repo", "178", "--input", "threads.json", "--format", "markdown"],
    {}
  );

  assert.equal(configuration.outputFormat, "markdown");
});

test("getConfiguration parses an expected unresolved thread count", () => {
  const configuration = getConfiguration(
    ["octo/repo", "178", "--input", "threads.json", "--expect-count", "4"],
    {}
  );

  assert.equal(configuration.expectedCount, 4);
});

test("getConfiguration resolves the inventory doc output path", () => {
  const configuration = getConfiguration(
    [
      "octo/repo",
      "178",
      "--input",
      "threads.json",
      "--write-inventory-doc",
      "docs/pr-178-unresolved-threads.md",
    ],
    {}
  );

  assert.equal(
    configuration.inventoryDocPath,
    path.resolve("docs/pr-178-unresolved-threads.md")
  );
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
            url: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
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
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      comments: [
        {
          id: "COMMENT_1",
          author: "reviewer",
          body: "First line. Second line.",
          createdAt: "2025-01-01T00:00:00Z",
          url: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
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
      expectedCount: null,
      inputPath: "threads.json",
      inventoryDocPath: null,
      outputFormat: "text",
      positional: ["octo/repo", "178"],
    }
  );
});

test("parseCommandLineArguments accepts an explicit output format", () => {
  assert.deepEqual(
    parseCommandLineArguments(["octo/repo", "178", "--input", "threads.json", "--format", "json"]),
    {
      expectedCount: null,
      inputPath: "threads.json",
      inventoryDocPath: null,
      outputFormat: "json",
      positional: ["octo/repo", "178"],
    }
  );
});

test("parseCommandLineArguments accepts an explicit expected count", () => {
  assert.deepEqual(
    parseCommandLineArguments([
      "octo/repo",
      "178",
      "--input",
      "threads.json",
      "--expect-count",
      "0",
    ]),
    {
      expectedCount: "0",
      inputPath: "threads.json",
      inventoryDocPath: null,
      outputFormat: "text",
      positional: ["octo/repo", "178"],
    }
  );
});

test("parseCommandLineArguments accepts an inventory doc output path", () => {
  assert.deepEqual(
    parseCommandLineArguments([
      "octo/repo",
      "178",
      "--input",
      "threads.json",
      "--write-inventory-doc",
      "docs/pr-178-unresolved-threads.md",
    ]),
    {
      expectedCount: null,
      inputPath: "threads.json",
      inventoryDocPath: "docs/pr-178-unresolved-threads.md",
      outputFormat: "text",
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

test("extractThreadsFromSnapshot supports reviewThreads edge collections", () => {
  assert.deepEqual(
    extractThreadsFromSnapshot({
      reviewThreads: {
        edges: [
          { node: { id: "THREAD_1" } },
          { node: { id: "THREAD_2" } },
          { node: null },
        ],
      },
    }),
    [{ id: "THREAD_1" }, { id: "THREAD_2" }]
  );
});

test("extractThreadsFromSnapshot supports pullRequest reviewThreads node collections", () => {
  assert.deepEqual(
    extractThreadsFromSnapshot({
      pullRequest: {
        reviewThreads: {
          nodes: [{ id: "THREAD_1" }, { id: "THREAD_2" }],
        },
      },
    }),
    [{ id: "THREAD_1" }, { id: "THREAD_2" }]
  );
});

test("extractThreadsFromSnapshot supports repository pullRequest node collections", () => {
  assert.deepEqual(
    extractThreadsFromSnapshot({
      repository: {
        pullRequest: {
          reviewThreads: {
            nodes: [{ id: "THREAD_1" }, { id: "THREAD_2" }],
          },
        },
      },
    }),
    [{ id: "THREAD_1" }, { id: "THREAD_2" }]
  );
});

test("extractThreadsFromSnapshot supports GraphQL node reviewThreads collections", () => {
  assert.deepEqual(
    extractThreadsFromSnapshot({
      data: {
        node: {
          reviewThreads: {
            edges: [{ node: { id: "THREAD_1" } }, { node: { id: "THREAD_2" } }],
          },
        },
      },
    }),
    [{ id: "THREAD_1" }, { id: "THREAD_2" }]
  );
});

test("extractThreadsFromSnapshot supports GraphQL edge collections", () => {
  assert.deepEqual(
    extractThreadsFromSnapshot({
      data: {
        repository: {
          pullRequest: {
            reviewThreads: {
              edges: [{ node: { id: "THREAD_1" } }, { node: { id: "THREAD_2" } }],
            },
          },
        },
      },
    }),
    [{ id: "THREAD_1" }, { id: "THREAD_2" }]
  );
});

test("normalizeSnapshotThreadCollection returns node payloads and filters empty edges", () => {
  assert.deepEqual(
    normalizeSnapshotThreadCollection({
      edges: [{ node: { id: "THREAD_1" } }, { node: null }, {}],
    }),
    [{ id: "THREAD_1" }]
  );
  assert.equal(normalizeSnapshotThreadCollection({ reviewThreads: [] }), null);
});

test("loadReviewThreadsFromFile wraps JSON parsing failures with the input path", () => {
  assert.throws(
    () =>
      loadReviewThreadsFromFile("broken-review-threads.json", {
        readFileSync: () => "{not valid json",
      }),
    /Unable to load review threads from "broken-review-threads\.json":/
  );
});

test("extractThreadsFromSnapshot rejects unsupported snapshot shapes", () => {
  assert.throws(
    () => extractThreadsFromSnapshot({ data: { repository: {} } }),
    /supported thread collection/
  );
});

test("fetchAllReviewThreads paginates until GitHub reports no additional pages", async () => {
  const requests = [];
  const threads = await fetchAllReviewThreads(
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      token: "token-value",
    },
    {
      requestGraphql: async ({ variables }) => {
        requests.push(variables);

        if (variables.after === null) {
          return {
            repository: {
              pullRequest: {
                reviewThreads: {
                  nodes: [{ id: "THREAD_1" }],
                  pageInfo: {
                    hasNextPage: true,
                    endCursor: "cursor-1",
                  },
                },
              },
            },
          };
        }

        assert.equal(variables.after, "cursor-1");
        return {
          repository: {
            pullRequest: {
              reviewThreads: {
                nodes: [{ id: "THREAD_2" }],
                pageInfo: {
                  hasNextPage: false,
                  endCursor: null,
                },
              },
            },
          },
        };
      },
    }
  );

  assert.deepEqual(threads, [{ id: "THREAD_1" }, { id: "THREAD_2" }]);
  assert.deepEqual(requests, [
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      after: null,
    },
    {
      owner: "stranske",
      repo: "trip-planner",
      prNumber: 178,
      after: "cursor-1",
    },
  ]);
});

test("fetchAllReviewThreads fails when GitHub returns no pull request node", async () => {
  await assert.rejects(
    () =>
      fetchAllReviewThreads(
        {
          owner: "stranske",
          repo: "trip-planner",
          prNumber: 178,
          token: "token-value",
        },
        {
          requestGraphql: async () => ({
            repository: {
              pullRequest: null,
            },
          }),
        }
      ),
    /Pull request #178 was not found in stranske\/trip-planner\./
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

test("buildMarkdownThreadSection emits a template-ready thread block", () => {
  assert.deepEqual(
    buildMarkdownThreadSection(
      {
        id: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        path: "trip_planner/example.py",
        line: 17,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please keep this branch explicit.",
          },
        ],
      },
      0
    ),
    [
      "",
      "### Thread 1",
      "",
      "- Thread ID: THREAD_1",
      "- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      "- Location: trip_planner/example.py:17",
      "- Classification:",
      "- Follow-up PR:",
      "- Rationale:",
      "- Content: reviewer: Please keep this branch explicit.",
      "- Outdated: no",
    ]
  );
});

test("buildMarkdownThreadSection preserves existing triage metadata when available", () => {
  assert.deepEqual(
    buildMarkdownThreadSection(
      {
        id: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        path: "trip_planner/example.py",
        line: 17,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please keep this branch explicit.",
          },
        ],
      },
      0,
      {
        threadId: "THREAD_1",
        classification: "fix",
        followUpPr: "https://github.com/stranske/trip-planner/pull/581",
        rationale: "A follow-up patch is already in flight.",
      }
    ),
    [
      "",
      "### Thread 1",
      "",
      "- Thread ID: THREAD_1",
      "- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      "- Location: trip_planner/example.py:17",
      "- Classification: fix",
      "- Follow-up PR: https://github.com/stranske/trip-planner/pull/581",
      "- Rationale: A follow-up patch is already in flight.",
      "- Content: reviewer: Please keep this branch explicit.",
      "- Outdated: no",
    ]
  );
});

test("formatUnresolvedThreadsAsMarkdown emits a doc-ready inventory skeleton", () => {
  const report = formatUnresolvedThreadsAsMarkdown("stranske/trip-planner", 178, [
    {
      id: "THREAD_1",
      isOutdated: true,
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
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

  assert.match(report, /# PR #178 Unresolved Thread Inventory/);
  assert.match(report, /- Thread ID: THREAD_1/);
  assert.match(
    report,
    /- Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/
  );
  assert.match(report, /- Location: scripts\/list_unresolved_pr_threads\.js:99/);
  assert.match(report, /- Classification:/);
  assert.match(report, /- Follow-up PR:/);
  assert.match(report, /- Rationale:/);
  assert.match(report, /- Content: reviewer: Please handle pagination\./);
  assert.match(report, /- Outdated: yes/);
});

test("formatUnresolvedThreadsAsMarkdown uses the requested pull request number in the title", () => {
  const report = formatUnresolvedThreadsAsMarkdown("stranske/trip-planner", 581, []);

  assert.match(report, /# PR #581 Unresolved Thread Inventory/);
});

test("formatUnresolvedThreadsAsMarkdown output can be parsed by the inventory tooling", () => {
  const report = formatUnresolvedThreadsAsMarkdown("stranske/trip-planner", 178, [
    {
      id: "THREAD_1",
      isOutdated: false,
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      path: "trip_planner/example.py",
      line: 17,
      comments: [
        {
          author: "reviewer-a",
          body: "Please keep this branch explicit.",
        },
      ],
    },
  ]);

  assert.deepEqual(parseThreadInventory(report), [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: null,
      followUpPr: null,
      rationale: null,
      content: "reviewer-a: Please keep this branch explicit.",
      outdated: false,
    },
  ]);
});

test("mergeInventoryIntoDocument replaces the placeholder template with generated threads", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Template

### Thread 1

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
`,
    [
      {
        id: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        path: "trip_planner/example.py",
        line: 17,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please keep this branch explicit.",
          },
        ],
      },
    ]
  );

  assert.match(mergedDocument, /^# PR #178 Unresolved Thread Inventory/m);
  assert.match(mergedDocument, /Intro paragraph\./);
  assert.match(mergedDocument, /## Thread Inventory/);
  assert.doesNotMatch(mergedDocument, /## Thread Template/);
  assert.match(mergedDocument, /- Thread ID: THREAD_1/);
});

test("mergeInventoryIntoDocument preserves manual classifications and follow-up PR links", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: old/path.py:10
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Existing manual triage should survive snapshot refreshes.
- Content: reviewer: stale text
- Outdated: no
`,
    [
      {
        id: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        path: "trip_planner/example.py",
        line: 17,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please keep this branch explicit.",
          },
        ],
      },
    ]
  );

  assert.match(mergedDocument, /- Classification: fix/);
  assert.match(
    mergedDocument,
    /- Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(
    mergedDocument,
    /- Rationale: Existing manual triage should survive snapshot refreshes\./
  );
  assert.match(mergedDocument, /- Location: trip_planner\/example\.py:17/);
  assert.match(mergedDocument, /- Content: reviewer: Please keep this branch explicit\./);
});

test("writeInventoryDocument updates a doc file in place", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "thread-inventory-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Template

### Thread 1

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
`,
    "utf8"
  );

  writeInventoryDocument(docPath, [
    {
      id: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      path: "trip_planner/example.py",
      line: 17,
      isOutdated: false,
      comments: [
        {
          author: "reviewer",
          body: "Please keep this branch explicit.",
        },
      ],
    },
  ]);

  const updatedDocument = fs.readFileSync(docPath, "utf8");
  assert.match(updatedDocument, /## Thread Inventory/);
  assert.match(updatedDocument, /- Thread ID: THREAD_1/);
});

test("formatThreadContent condenses multiple comments into a single content field", () => {
  assert.equal(
    formatThreadContent([
      { author: "reviewer-a", body: "First note." },
      { author: "reviewer-b", body: "Second note." },
    ]),
    "reviewer-a: First note. | reviewer-b: Second note."
  );

  assert.equal(formatThreadContent([]), "No thread comments returned by the API.");
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
    /### Thread 1/
  );
});

test("validateExpectedCount enforces the requested unresolved thread count", () => {
  assert.doesNotThrow(() =>
    validateExpectedCount(
      [
        { id: "THREAD_1", comments: [] },
        { id: "THREAD_2", comments: [] },
      ],
      2
    )
  );

  assert.throws(
    () =>
      validateExpectedCount(
        [{ id: "THREAD_1", comments: [] }],
        0
      ),
    /Expected 0 unresolved review thread\(s\), found 1\./
  );
});
