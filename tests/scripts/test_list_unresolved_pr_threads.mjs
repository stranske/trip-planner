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
  buildBlankInventoryTemplate,
  buildBlankMarkdownThreadSection,
  buildMarkdownThreadSection,
  collectResolvedInventoryEntries,
  deduplicateInventoryEntries,
  extractUnresolvedThreads,
  extractInventoryDocumentState,
  extractThreadsFromSnapshot,
  fetchAllReviewThreads,
  findExistingInventoryEntry,
  findSectionBounds,
  formatOutput,
  formatThreadContent,
  formatUnresolvedThreadsAsJson,
  formatUnresolvedThreadsAsMarkdown,
  formatUnresolvedThreadsReport,
  findInventorySectionRange,
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

test("buildMarkdownThreadSection preserves the documented original thread URL when a refresh omits comment URLs", () => {
  assert.deepEqual(
    buildMarkdownThreadSection(
      {
        id: "THREAD_1",
        originalThreadUrl: null,
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
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        classification: "fix",
        followUpPr: "https://github.com/stranske/trip-planner/pull/581",
        rationale: "Existing manual triage should survive incomplete refresh data.",
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
      "- Rationale: Existing manual triage should survive incomplete refresh data.",
      "- Content: reviewer: Please keep this branch explicit.",
      "- Outdated: no",
    ]
  );
});

test("buildBlankMarkdownThreadSection emits the verifier-compatible inventory shape", () => {
  assert.deepEqual(buildBlankMarkdownThreadSection(0), [
    "",
    "### Thread 1",
    "",
    "- Thread ID:",
    "- Original Thread URL:",
    "- Location:",
    "- Classification:",
    "- Follow-up PR:",
    "- Rationale:",
    "- Content:",
    "- Outdated:",
  ]);
});

test("buildBlankInventoryTemplate includes outdated placeholders for each thread", () => {
  const template = buildBlankInventoryTemplate(2);

  assert.match(template, /^## Thread Template/m);
  assert.match(template, /### Thread 1/);
  assert.match(template, /### Thread 2/);
  assert.equal((template.match(/- Outdated:/g) || []).length, 2);
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

${buildBlankInventoryTemplate(1)}`,
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

test("findInventorySectionRange isolates only the inventory block when trailing sections exist", () => {
  const document = `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1

## Follow-up Notes

This section should stay below the generated inventory.
`;

  assert.deepEqual(findInventorySectionRange(document), {
    start: document.indexOf("## Thread Inventory"),
    end: document.indexOf("## Follow-up Notes"),
  });
});

test("findSectionBounds isolates a named inventory subsection", () => {
  const document = `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_OLD
`;

  assert.deepEqual(findSectionBounds(document, "## Thread Inventory"), {
    start: document.indexOf("## Thread Inventory"),
    end: document.indexOf("## Resolved Thread Inventory"),
  });
  assert.deepEqual(findSectionBounds(document, "## Resolved Thread Inventory"), {
    start: document.indexOf("## Resolved Thread Inventory"),
    end: document.length,
  });
});

test("extractInventoryDocumentState ignores blank template placeholders and keeps resolved history separate", () => {
  const state = extractInventoryDocumentState(`# PR #178 Unresolved Thread Inventory

## Thread Inventory

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

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:23
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Existing triage should remain visible.
- Content: reviewer: Please extract a helper.
- Outdated: no

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_OLD
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Follow-up PR:
- Rationale: Historical resolution should stay separate.
- Content: reviewer: This thread was already resolved.
- Outdated: no
`);

  assert.deepEqual(state.currentThreads.map((thread) => thread.threadId), ["THREAD_2"]);
  assert.deepEqual(state.resolvedThreads.map((thread) => thread.threadId), ["THREAD_OLD"]);
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

test("findExistingInventoryEntry falls back to matching original thread URL and section order", () => {
  const existingThreads = [
    {
      threadId: null,
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/old.md:10",
      classification: "disposition",
      followUpPr: null,
      rationale: "URL match should survive even before thread IDs are filled in.",
      content: "reviewer: stale text",
      outdated: false,
    },
    {
      threadId: null,
      originalThreadUrl: null,
      location: "docs/second.md:20",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Index fallback should preserve this section.",
      content: "reviewer: another stale text",
      outdated: false,
    },
  ];

  assert.equal(
    findExistingInventoryEntry(
      existingThreads,
      {
        id: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      },
      0
    ),
    existingThreads[0]
  );
  assert.equal(
    findExistingInventoryEntry(
      existingThreads,
      {
        id: "THREAD_2",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      },
      1
    ),
    existingThreads[1]
  );
});

test("mergeInventoryIntoDocument preserves manual triage before thread IDs are recorded", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID:
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: old/path.py:10
- Classification: disposition
- Follow-up PR:
- Rationale: URL matching should preserve this triage.
- Content: reviewer: stale text
- Outdated: no

### Thread 2

- Thread ID:
- Original Thread URL:
- Location: old/other.py:20
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Index fallback should preserve this triage.
- Content: reviewer: older text
- Outdated: yes
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
      {
        id: "THREAD_2",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        path: "trip_planner/other.py",
        line: 23,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please extract a helper.",
          },
        ],
      },
    ]
  );

  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_1/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Classification: disposition/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Rationale: URL matching should preserve this triage\./);
  assert.match(mergedDocument, /### Thread 2[\s\S]*- Thread ID: THREAD_2/);
  assert.match(mergedDocument, /### Thread 2[\s\S]*- Classification: fix/);
  assert.match(
    mergedDocument,
    /### Thread 2[\s\S]*- Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(mergedDocument, /### Thread 2[\s\S]*- Rationale: Index fallback should preserve this triage\./);
  assert.match(mergedDocument, /### Thread 2[\s\S]*- Content: reviewer: Please extract a helper\./);
});

test("writeInventoryDocument updates a doc file in place", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "thread-inventory-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

${buildBlankInventoryTemplate(1)}`,
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

test("mergeInventoryIntoDocument preserves documented triage when no unresolved threads remain", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Existing fix triage should remain visible after the thread is resolved.
- Content: reviewer: Please keep this branch explicit.
- Outdated: no
`,
    []
  );

  assert.match(mergedDocument, /## Thread Inventory\n\nNo unresolved inline review threads found\./);
  assert.match(mergedDocument, /## Resolved Thread Inventory/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_1/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Classification: fix/);
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Follow-up PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/581/
  );
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Rationale: Existing fix triage should remain visible after the thread is resolved\./
  );
});

test("collectResolvedInventoryEntries returns documented threads that are no longer unresolved", () => {
  const existingThreads = [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "trip_planner/example.py:17",
      classification: "fix",
      followUpPr: "https://github.com/stranske/trip-planner/pull/581",
      rationale: "Still unresolved.",
      content: "reviewer: Please keep this branch explicit.",
      outdated: false,
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      location: "trip_planner/other.py:23",
      classification: "disposition",
      followUpPr: null,
      rationale: "This one was already resolved.",
      content: "reviewer: Please extract a helper.",
      outdated: false,
    },
  ];

  const resolvedThreads = collectResolvedInventoryEntries(existingThreads, [
    {
      id: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
    },
  ]);

  assert.deepEqual(resolvedThreads, [existingThreads[1]]);
});

test("deduplicateInventoryEntries keeps the first copy of repeated thread metadata", () => {
  const entries = [
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      classification: "fix",
    },
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      classification: "disposition",
    },
    {
      threadId: "THREAD_2",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
      classification: "disposition",
    },
  ];

  assert.deepEqual(deduplicateInventoryEntries(entries), [entries[0], entries[2]]);
});

test("writeInventoryDocument keeps resolved thread inventory when refreshing to zero unresolved threads", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "thread-inventory-zero-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Follow-up PR:
- Rationale: The reviewer concern was handled in the original PR discussion.
- Content: reviewer: Please keep this branch explicit.
- Outdated: no
`,
    "utf8"
  );

  writeInventoryDocument(docPath, []);

  const updatedDocument = fs.readFileSync(docPath, "utf8");
  assert.match(updatedDocument, /No unresolved inline review threads found\./);
  assert.match(updatedDocument, /## Resolved Thread Inventory/);
  assert.match(updatedDocument, /### Thread 1[\s\S]*- Classification: disposition/);
  assert.match(
    updatedDocument,
    /### Thread 1[\s\S]*- Rationale: The reviewer concern was handled in the original PR discussion\./
  );
});

test("writeInventoryDocument replaces the inventory block after a non-inventory status section", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "thread-inventory-status-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Status

Inventory has not been populated yet.

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

## Follow-up Notes

Keep this section after inventory refresh.
`,
    "utf8"
  );

  writeInventoryDocument(docPath, [
    {
      id: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      path: "scripts/list_unresolved_pr_threads.js",
      line: 121,
      isOutdated: false,
      comments: [
        {
          author: "reviewer",
          body: "Please preserve the inventory section in place.",
        },
      ],
    },
  ]);

  const updatedDocument = fs.readFileSync(docPath, "utf8");
  assert.match(updatedDocument, /## Status/);
  assert.match(updatedDocument, /## Thread Inventory/);
  assert.doesNotMatch(updatedDocument, /## Thread Template/);
  assert.match(updatedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_1/);
  assert.match(updatedDocument, /## Follow-up Notes/);
  assert.match(updatedDocument, /Keep this section after inventory refresh\./);
});

test("mergeInventoryIntoDocument preserves trailing sections below the inventory block", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: old/path.py:10
- Classification: disposition
- Follow-up PR:
- Rationale: Existing triage should survive inventory refreshes.
- Content: reviewer: stale text
- Outdated: no

## Follow-up Notes

- Keep these notes after refresh.
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

  assert.match(mergedDocument, /## Thread Inventory/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Location: trip_planner\/example\.py:17/);
  assert.match(mergedDocument, /## Follow-up Notes/);
  assert.match(mergedDocument, /Keep these notes after refresh\./);
});

test("mergeInventoryIntoDocument preserves resolved history when only some threads remain unresolved", () => {
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
- Rationale: This fix is still pending.
- Content: reviewer: stale unresolved text
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: old/resolved.py:20
- Classification: disposition
- Follow-up PR:
- Rationale: This discussion was already handled in the PR conversation.
- Content: reviewer: stale resolved text
- Outdated: yes
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

  assert.match(mergedDocument, /## Thread Inventory/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_1/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Classification: fix/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Location: trip_planner\/example\.py:17/);
  assert.match(mergedDocument, /## Resolved Thread Inventory/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_2/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Classification: disposition/);
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Rationale: This discussion was already handled in the PR conversation\./
  );
});

test("mergeInventoryIntoDocument does not reuse resolved-only entries as fallback matches for active unresolved threads", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

No unresolved inline review threads found.

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_OLD
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: old/path.py:10
- Classification: disposition
- Follow-up PR:
- Rationale: Historical resolved triage should not bleed into new unresolved threads.
- Content: reviewer: stale resolved content
- Outdated: no
`,
    [
      {
        id: "THREAD_NEW",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        path: "scripts/list_unresolved_pr_threads.js",
        line: 121,
        isOutdated: false,
        comments: [
          {
            author: "reviewer",
            body: "Please handle the latest unresolved case.",
          },
        ],
      },
    ]
  );

  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_NEW/);
  const [unresolvedSection] = mergedDocument.split("## Resolved Thread Inventory");
  assert.match(unresolvedSection, /### Thread 1[\s\S]*- Classification:\s*$/m);
  assert.match(
    unresolvedSection,
    /### Thread 1[\s\S]*- Content: reviewer: Please handle the latest unresolved case\./
  );
  assert.match(mergedDocument, /## Resolved Thread Inventory/);
  assert.match(mergedDocument, /THREAD_OLD/);
  assert.doesNotMatch(
    unresolvedSection,
    /### Thread 1[\s\S]*Historical resolved triage should not bleed into new unresolved threads\./
  );
});

test("mergeInventoryIntoDocument does not preserve blank template entries as resolved history", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

${buildBlankInventoryTemplate(4)}`,
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

  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_1/);
  assert.doesNotMatch(mergedDocument, /## Resolved Thread Inventory/);
});

test("mergeInventoryIntoDocument preserves resolved-only history when unresolved threads return", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_OLD
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: disposition
- Follow-up PR:
- Rationale: Historical triage should be replaced by the latest unresolved snapshot.
- Content: reviewer: Legacy resolved thread content.
- Outdated: no
`,
    [
      {
        id: "THREAD_NEW",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        path: "scripts/list_unresolved_pr_threads.js",
        line: 121,
        isOutdated: true,
        comments: [
          {
            author: "reviewer",
            body: "Please handle the latest unresolved case.",
          },
        ],
      },
    ]
  );

  assert.match(mergedDocument, /## Thread Inventory/);
  assert.match(mergedDocument, /### Thread 1[\s\S]*- Thread ID: THREAD_NEW/);
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r2/
  );
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Content: reviewer: Please handle the latest unresolved case\./
  );
  assert.match(mergedDocument, /## Resolved Thread Inventory/);
  assert.match(mergedDocument, /THREAD_OLD/);
});

test("mergeInventoryIntoDocument deduplicates repeated resolved entries when no unresolved threads remain", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: Keep the active-thread version of this triage.
- Content: reviewer: Please keep this branch explicit.
- Outdated: no

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: stale/path.py:99
- Classification: disposition
- Follow-up PR:
- Rationale: Older resolved copy should not be duplicated.
- Content: reviewer: stale duplicate
- Outdated: yes
`,
    []
  );

  const threadIdMatches = mergedDocument.match(/- Thread ID: THREAD_1/g) || [];

  assert.equal(threadIdMatches.length, 1);
  assert.match(
    mergedDocument,
    /### Thread 1[\s\S]*- Rationale: Keep the active-thread version of this triage\./
  );
  assert.doesNotMatch(mergedDocument, /Older resolved copy should not be duplicated\./);
});

test("mergeInventoryIntoDocument deduplicates historical resolved entries that were already moved out of the current inventory", () => {
  const mergedDocument = mergeInventoryIntoDocument(
    `# PR #178 Unresolved Thread Inventory

Intro paragraph.

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: trip_planner/example.py:17
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: This thread is still unresolved.
- Content: reviewer: Please keep this branch explicit.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: trip_planner/other.py:22
- Classification: disposition
- Follow-up PR:
- Rationale: This thread should be moved to resolved history once it drops out of the snapshot.
- Content: reviewer: Please extract a helper.
- Outdated: yes

## Resolved Thread Inventory

### Thread 1

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: stale/other.py:20
- Classification: disposition
- Follow-up PR:
- Rationale: Older resolved copy should not be retained twice.
- Content: reviewer: stale duplicate
- Outdated: yes
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

  const threadIdMatches = mergedDocument.match(/- Thread ID: THREAD_2/g) || [];

  assert.equal(threadIdMatches.length, 1);
  assert.match(
    mergedDocument,
    /## Resolved Thread Inventory[\s\S]*- Rationale: This thread should be moved to resolved history once it drops out of the snapshot\./
  );
  assert.doesNotMatch(mergedDocument, /Older resolved copy should not be retained twice\./);
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
