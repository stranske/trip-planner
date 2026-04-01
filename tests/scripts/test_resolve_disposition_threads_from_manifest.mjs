import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildGhGraphqlArgs,
  convertInventoryEntryToSnapshotThread,
  DEFAULT_DOC_PATH,
  DEFAULT_MANIFEST_PATH,
  executeManifestThreads,
  formatExecutionReport,
  loadManifest,
  parseInventoryContent,
  parseInventoryLocation,
  parseCliArguments,
  selectManifestThreads,
  updateInventoryDocumentAfterResolution,
  validateManifestThread,
  writeRemainingSnapshot,
} = require(path.join(repoRoot, "scripts/resolve_disposition_threads_from_manifest.js"));
const {
  buildDispositionManifestEntry,
} = require(path.join(repoRoot, "scripts/list_disposition_threads_from_doc.js"));

test("buildDispositionManifestEntry includes structured GraphQL payloads", () => {
  const entry = buildDispositionManifestEntry(
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
    },
    0,
    "/tmp/disposition"
  );

  assert.equal(entry.threadId, "THREAD_1");
  assert.match(entry.replyQuery, /AddPullRequestReviewThreadReply/);
  assert.deepEqual(entry.replyVariables, {
    threadId: "THREAD_1",
    body: [
      "The existing behavior is intentional.",
      "",
      "Context from unresolved thread: reviewer: Please change the template wording.",
    ].join("\n"),
  });
  assert.match(entry.resolveQuery, /ResolveReviewThread/);
  assert.deepEqual(entry.resolveVariables, { threadId: "THREAD_1" });
});

test("parseCliArguments parses execution, filtering, and result output options", () => {
  assert.deepEqual(
    parseCliArguments([
      "--manifest",
      "tmp/manifest.json",
      "--execute",
      "--doc",
      "docs/pr-178-unresolved-threads.md",
      "--write-remaining-snapshot",
      "tmp/remaining-threads.json",
      "--write-acceptance-report",
      "tmp/acceptance.txt",
      "--thread-id",
      "THREAD_2",
      "--thread-index",
      "3",
      "--write-results",
      "tmp/results.json",
      "--github-ui-confirmed",
      "--format",
      "json",
    ]),
    {
      manifestPath: path.resolve("tmp/manifest.json"),
      execute: true,
      outputFormat: "json",
      resultsPath: "tmp/results.json",
      remainingSnapshotPath: "tmp/remaining-threads.json",
      acceptanceReportPath: "tmp/acceptance.txt",
      docPath: DEFAULT_DOC_PATH,
      threadId: "THREAD_2",
      threadIndex: 3,
      githubUiConfirmed: true,
    }
  );

  assert.equal(DEFAULT_MANIFEST_PATH, path.resolve(".tmp/pr-thread-disposition/manifest.json"));
});

test("parseCliArguments rejects unknown options and invalid values", () => {
  assert.throws(() => parseCliArguments(["--unknown"]), /Unknown option: --unknown/);
  assert.throws(() => parseCliArguments(["--thread-id"]), /requires a value/);
  assert.throws(() => parseCliArguments(["--thread-index", "0"]), /positive integer/);
  assert.throws(() => parseCliArguments(["--format", "markdown"]), /one of "text" or "json"/);
});

test("loadManifest requires a threads array", () => {
  assert.throws(
    () =>
      loadManifest("/tmp/manifest.json", {
        readFileSync: () => JSON.stringify({ count: 1 }),
      }),
    /must contain a "threads" array/
  );
});

test("validateManifestThread reports missing structured payload fields", () => {
  assert.deepEqual(validateManifestThread({}, 0), [
    "Thread 1 is missing threadId.",
    "Thread 1 is missing replyQuery.",
    "Thread 1 is missing replyVariables.",
    "Thread 1 is missing resolveQuery.",
    "Thread 1 is missing resolveVariables.",
  ]);
});

test("selectManifestThreads can filter by thread id or index", () => {
  const manifest = {
    threads: [{ threadId: "THREAD_1" }, { threadId: "THREAD_2" }],
  };

  assert.deepEqual(selectManifestThreads(manifest, { threadId: "THREAD_2" }), [
    { threadId: "THREAD_2", manifestThreadNumber: 2 },
  ]);
  assert.deepEqual(selectManifestThreads(manifest, { threadIndex: 1 }), [
    { threadId: "THREAD_1", manifestThreadNumber: 1 },
  ]);
  assert.throws(
    () => selectManifestThreads(manifest, { threadId: "THREAD_3" }),
    /No manifest threads matched thread ID "THREAD_3"/
  );
});

test("buildGhGraphqlArgs converts GraphQL variables into gh api args", () => {
  assert.deepEqual(buildGhGraphqlArgs("query Example", { threadId: "THREAD_1", body: "hello" }), [
    "api",
    "graphql",
    "-f",
    "query=query Example",
    "-F",
    "threadId=THREAD_1",
    "-F",
    "body=hello",
  ]);
});

test("inventory helpers preserve location and comment metadata when rebuilding active threads", () => {
  assert.deepEqual(parseInventoryLocation("src/file.js:10"), {
    path: "src/file.js",
    line: 10,
  });
  assert.deepEqual(parseInventoryLocation("src/file.js:unknown"), {
    path: "src/file.js",
    line: null,
  });
  assert.deepEqual(parseInventoryContent("reviewer: First note | author-two: Second note"), [
    {
      id: "inventory-comment-1",
      author: "reviewer",
      body: "First note",
    },
    {
      id: "inventory-comment-2",
      author: "author-two",
      body: "Second note",
    },
  ]);
  assert.deepEqual(
    convertInventoryEntryToSnapshotThread({
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "src/file.js:10",
      content: "reviewer: First note | author-two: Second note",
      outdated: false,
    }),
    {
      id: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      path: "src/file.js",
      line: 10,
      isOutdated: false,
      comments: [
        {
          id: "inventory-comment-1",
          author: "reviewer",
          body: "First note",
        },
        {
          id: "inventory-comment-2",
          author: "author-two",
          body: "Second note",
        },
      ],
    }
  );
});

test("executeManifestThreads returns a dry-run report with resolved script paths", async () => {
  const manifestDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-dry-run-"));
  const manifestPath = path.join(manifestDir, "manifest.json");
  fs.writeFileSync(
    manifestPath,
    `${JSON.stringify(
      {
        threads: [
          {
            threadId: "THREAD_1",
            originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
            location: "src/file.js:10",
            scriptPath: "scripts/thread-1.sh",
            replyQuery: "mutation Reply",
            replyVariables: { threadId: "THREAD_1", body: "Disposition" },
            resolveQuery: "mutation Resolve",
            resolveVariables: { threadId: "THREAD_1" },
          },
        ],
      },
      null,
      2
    )}\n`
  );

  const report = await executeManifestThreads({ manifestPath, execute: false });

  assert.equal(report.threadCount, 1);
  assert.equal(report.results[0].mode, "dry-run");
  assert.equal(report.results[0].scriptPath, path.join(manifestDir, "scripts/thread-1.sh"));
  assert.match(report.results[0].replyCommand, /^gh api graphql -f query=mutation Reply/);
  assert.match(report.results[0].resolveCommand, /^gh api graphql -f query=mutation Resolve/);
});

test("executeManifestThreads can execute reply and resolve commands in sequence", async () => {
  const manifest = {
    threads: [
      {
        threadId: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        location: "src/file.js:10",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const spawnCalls = [];
  const report = await executeManifestThreads(
    {
      manifestPath: "/tmp/manifest.json",
      execute: true,
    },
    {
      readFileSync: () => JSON.stringify(manifest),
      spawnSync: (_command, args) => {
        spawnCalls.push(args);
        return {
          status: 0,
          stdout: `ok:${args[3]}`,
          stderr: "",
        };
      },
    }
  );

  assert.equal(spawnCalls.length, 2);
  assert.deepEqual(spawnCalls[0], [
    "api",
    "graphql",
    "-f",
    "query=mutation Reply",
    "-F",
    "threadId=THREAD_1",
    "-F",
    "body=Disposition",
  ]);
  assert.deepEqual(spawnCalls[1], [
    "api",
    "graphql",
    "-f",
    "query=mutation Resolve",
    "-F",
    "threadId=THREAD_1",
  ]);
  assert.equal(report.results[0].replyExitStatus, 0);
  assert.equal(report.results[0].resolveExitStatus, 0);
});

test("writeRemainingSnapshot writes a list_unresolved_pr_threads compatible payload", () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "remaining-thread-snapshot-"));
  const snapshotPath = path.join(tempDir, "remaining.json");

  writeRemainingSnapshot(snapshotPath, [
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
          body: "Please keep this open.",
        },
      ],
    },
  ]);

  assert.deepEqual(JSON.parse(fs.readFileSync(snapshotPath, "utf8")), {
    unresolvedThreads: [
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
            body: "Please keep this open.",
          },
        ],
      },
    ],
  });
});

test("executeManifestThreads can write a remaining unresolved-thread snapshot after execution", async () => {
  const manifestDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-snapshot-"));
  const manifestPath = path.join(manifestDir, "manifest.json");
  const docPath = path.join(manifestDir, "pr-178-unresolved-threads.md");
  const remainingSnapshotPath = "artifacts/remaining-threads.json";

  fs.writeFileSync(
    manifestPath,
    `${JSON.stringify(
      {
        threads: [
          {
            threadId: "THREAD_1",
            originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
            location: "src/file.js:10",
            replyQuery: "mutation Reply",
            replyVariables: { threadId: "THREAD_1", body: "Disposition" },
            resolveQuery: "mutation Resolve",
            resolveVariables: { threadId: "THREAD_1" },
          },
        ],
      },
      null,
      2
    )}\n`
  );
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The existing behavior is intentional.
- Content: reviewer: Keep this as-is.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: src/other.js:22
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Rationale: The follow-up fix is still pending merge.
- Content: reviewer: This still needs a patch.
- Outdated: no
`
  );

  const commands = [];
  const report = await executeManifestThreads(
    {
      manifestPath,
      execute: true,
      docPath,
      remainingSnapshotPath,
    },
    {
      spawnSync: (command, args) => {
        commands.push([command, ...args]);
        return { status: 0, stdout: '{"data":{"ok":true}}', stderr: "" };
      },
    }
  );

  const resolvedSnapshotPath = path.join(manifestDir, remainingSnapshotPath);
  assert.equal(commands.length, 2);
  assert.equal(report.remainingSnapshotPath, resolvedSnapshotPath);
  assert.equal(report.remainingSnapshotThreadCount, 1);
  assert.deepEqual(JSON.parse(fs.readFileSync(resolvedSnapshotPath, "utf8")), {
    unresolvedThreads: [
      {
        id: "THREAD_2",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
        path: "src/other.js",
        line: 22,
        isOutdated: false,
        comments: [
          {
            id: "inventory-comment-1",
            author: "reviewer",
            body: "This still needs a patch.",
          },
        ],
      },
    ],
  });
});

test("executeManifestThreads rejects remaining snapshot output without execution and doc context", async () => {
  const manifestDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-invalid-"));
  const manifestPath = path.join(manifestDir, "manifest.json");
  fs.writeFileSync(
    manifestPath,
    `${JSON.stringify(
      {
        threads: [
          {
            threadId: "THREAD_1",
            replyQuery: "mutation Reply",
            replyVariables: { threadId: "THREAD_1", body: "Disposition" },
            resolveQuery: "mutation Resolve",
            resolveVariables: { threadId: "THREAD_1" },
          },
        ],
      },
      null,
      2
    )}\n`
  );

  await assert.rejects(
    () =>
      executeManifestThreads({
        manifestPath,
        execute: false,
        remainingSnapshotPath: "artifacts/remaining.json",
      }),
    /requires both --execute and --doc/
  );
});

test("updateInventoryDocumentAfterResolution moves resolved threads out of the active inventory", () => {
  const docPath = path.join(os.tmpdir(), "pr-178-thread-inventory-update.md");
  const initialDocument = `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no

### Thread 2

- Thread ID: THREAD_2
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2
- Location: src/other.js:20
- Classification: disposition
- Follow-up PR:
- Rationale: The documented tradeoff is sufficient.
- Content: reviewer: Please add more context.
- Outdated: no
`;

  fs.writeFileSync(docPath, initialDocument, "utf8");

  const update = updateInventoryDocumentAfterResolution(docPath, ["THREAD_1"]);
  const updatedDocument = fs.readFileSync(docPath, "utf8");
  const [activeSection, resolvedSection = ""] = updatedDocument.split("## Resolved Thread Inventory");

  assert.equal(update.resolvedThreadCount, 1);
  assert.equal(update.remainingThreadCount, 1);
  assert.match(activeSection, /## Thread Inventory[\s\S]*THREAD_2/);
  assert.doesNotMatch(activeSection, /THREAD_1/);
  assert.match(resolvedSection, /THREAD_1/);
});

test("executeManifestThreads fails when reply execution fails", async () => {
  const manifest = {
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };

  await assert.rejects(
    () =>
      executeManifestThreads(
        {
          manifestPath: "/tmp/manifest.json",
          execute: true,
        },
        {
          readFileSync: () => JSON.stringify(manifest),
          spawnSync: () => ({
            status: 1,
            stdout: "",
            stderr: "authentication failed",
          }),
        }
      ),
    /reply command failed with exit code 1: authentication failed/
  );
});

test("executeManifestThreads updates the inventory document after successful execution when --doc is provided", async () => {
  const manifest = {
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const docPath = path.join(os.tmpdir(), "pr-178-thread-exec-update.md");
  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no
`,
    "utf8"
  );

  const report = await executeManifestThreads(
    {
      manifestPath: "/tmp/manifest.json",
      execute: true,
      docPath,
    },
    {
      readFileSync: (targetPath) =>
        targetPath === docPath ? fs.readFileSync(docPath, "utf8") : JSON.stringify(manifest),
      writeFileSync: (targetPath, content) => fs.writeFileSync(targetPath, content, "utf8"),
      spawnSync: () => ({
        status: 0,
        stdout: "ok",
        stderr: "",
      }),
    }
  );

  const updatedDocument = fs.readFileSync(docPath, "utf8");
  assert.equal(report.inventoryUpdate.resolvedThreadCount, 1);
  assert.equal(report.inventoryUpdate.remainingThreadCount, 0);
  assert.match(updatedDocument, /No unresolved inline review threads found\./);
  assert.match(updatedDocument, /## Resolved Thread Inventory[\s\S]*THREAD_1/);
});

test("executeManifestThreads writes inventory update details into the persisted results report", async () => {
  const manifest = {
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-results-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const resultsPath = path.join(tempDir, "results.json");

  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no
`,
    "utf8"
  );

  const report = await executeManifestThreads(
    {
      manifestPath: path.join(tempDir, "manifest.json"),
      execute: true,
      docPath,
      resultsPath,
    },
    {
      readFileSync: (targetPath) =>
        targetPath === docPath ? fs.readFileSync(docPath, "utf8") : JSON.stringify(manifest),
      writeFileSync: (targetPath, content) => fs.writeFileSync(targetPath, content, "utf8"),
      mkdirSync: (targetPath, options) => fs.mkdirSync(targetPath, options),
      spawnSync: () => ({
        status: 0,
        stdout: "ok",
        stderr: "",
      }),
    }
  );

  const persistedReport = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
  assert.equal(report.inventoryUpdate.resolvedThreadCount, 1);
  assert.deepEqual(report.remainingThreadsSnapshot, []);
  assert.deepEqual(persistedReport.inventoryUpdate, {
    docPath,
    resolvedThreadCount: 1,
    remainingThreadCount: 0,
  });
  assert.deepEqual(persistedReport.remainingThreadsSnapshot, []);
});

test("executeManifestThreads can write a post-resolution acceptance report", async () => {
  const manifest = {
    repositoryOwner: "stranske",
    repositoryName: "trip-planner",
    prNumber: 178,
    expectDocCount: 1,
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-acceptance-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const acceptanceReportPath = path.join(tempDir, "acceptance.txt");

  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no
`,
    "utf8"
  );

  const report = await executeManifestThreads(
    {
      manifestPath: path.join(tempDir, "manifest.json"),
      execute: true,
      docPath,
      acceptanceReportPath,
      outputFormat: "text",
      githubUiConfirmed: true,
    },
    {
      readFileSync: (targetPath) =>
        targetPath === docPath ? fs.readFileSync(docPath, "utf8") : JSON.stringify(manifest),
      writeFileSync: (targetPath, content) => fs.writeFileSync(targetPath, content, "utf8"),
      mkdirSync: (targetPath, options) => fs.mkdirSync(targetPath, options),
      spawnSync: () => ({
        status: 0,
        stdout: '{"data":{"ok":true}}',
        stderr: "",
      }),
    }
  );

  const acceptanceReport = fs.readFileSync(acceptanceReportPath, "utf8");
  assert.equal(report.acceptance.overallStatus, "pass");
  assert.equal(report.acceptance.unresolvedThreadCount, 0);
  assert.equal(report.acceptanceReportPath, acceptanceReportPath);
  assert.match(acceptanceReport, /Overall status: PASS/);
  assert.match(acceptanceReport, /review-thread snapshot verifies 0 unresolved thread\(s\)/i);
});

test("executeManifestThreads persists an embedded remaining-thread snapshot for later acceptance reruns", async () => {
  const manifest = {
    repositoryOwner: "stranske",
    repositoryName: "trip-planner",
    prNumber: 178,
    expectDocCount: 1,
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-embedded-results-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const resultsPath = path.join(tempDir, "results.json");
  const acceptanceReportPath = path.join(tempDir, "acceptance.txt");

  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no
`,
    "utf8"
  );

  const report = await executeManifestThreads(
    {
      manifestPath: path.join(tempDir, "manifest.json"),
      execute: true,
      docPath,
      resultsPath,
      acceptanceReportPath,
      outputFormat: "text",
      githubUiConfirmed: true,
    },
    {
      readFileSync: (targetPath) =>
        targetPath === docPath ? fs.readFileSync(docPath, "utf8") : JSON.stringify(manifest),
      writeFileSync: (targetPath, content) => fs.writeFileSync(targetPath, content, "utf8"),
      mkdirSync: (targetPath, options) => fs.mkdirSync(targetPath, options),
      spawnSync: () => ({
        status: 0,
        stdout: '{"data":{"ok":true}}',
        stderr: "",
      }),
    }
  );

  const persistedReport = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
  assert.deepEqual(report.remainingThreadsSnapshot, []);
  assert.deepEqual(persistedReport.remainingThreadsSnapshot, []);
  assert.equal(persistedReport.acceptance.inputPath, "<post-resolution inventory>");
});

test("executeManifestThreads derives the documented thread count for acceptance when older manifests omit it", async () => {
  const manifest = {
    repositoryOwner: "stranske",
    repositoryName: "trip-planner",
    prNumber: 178,
    threads: [
      {
        threadId: "THREAD_1",
        replyQuery: "mutation Reply",
        replyVariables: { threadId: "THREAD_1", body: "Disposition" },
        resolveQuery: "mutation Resolve",
        resolveVariables: { threadId: "THREAD_1" },
      },
    ],
  };
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-acceptance-fallback-"));
  const docPath = path.join(tempDir, "pr-178-unresolved-threads.md");
  const acceptanceReportPath = path.join(tempDir, "acceptance.txt");

  fs.writeFileSync(
    docPath,
    `# PR #178 Unresolved Thread Inventory

## Thread Inventory

### Thread 1

- Thread ID: THREAD_1
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r1
- Location: src/file.js:10
- Classification: disposition
- Follow-up PR:
- Rationale: The current behavior is intentional.
- Content: reviewer: Keep the existing wording.
- Outdated: no
`,
    "utf8"
  );

  const report = await executeManifestThreads(
    {
      manifestPath: path.join(tempDir, "manifest.json"),
      execute: true,
      docPath,
      acceptanceReportPath,
      outputFormat: "text",
      githubUiConfirmed: true,
    },
    {
      readFileSync: (targetPath) =>
        targetPath === docPath ? fs.readFileSync(docPath, "utf8") : JSON.stringify(manifest),
      writeFileSync: (targetPath, content) => fs.writeFileSync(targetPath, content, "utf8"),
      mkdirSync: (targetPath, options) => fs.mkdirSync(targetPath, options),
      spawnSync: () => ({
        status: 0,
        stdout: '{"data":{"ok":true}}',
        stderr: "",
      }),
    }
  );

  const acceptanceReport = fs.readFileSync(acceptanceReportPath, "utf8");
  assert.equal(report.acceptance.overallStatus, "pass");
  assert.equal(report.acceptance.expectDocCount, 1);
  assert.match(acceptanceReport, /records 1 complete thread entries/i);
});

test("executeManifestThreads rejects acceptance report output without execution and doc context", async () => {
  const manifestDir = fs.mkdtempSync(path.join(os.tmpdir(), "resolve-disposition-acceptance-invalid-"));
  const manifestPath = path.join(manifestDir, "manifest.json");
  fs.writeFileSync(
    manifestPath,
    `${JSON.stringify(
      {
        threads: [
          {
            threadId: "THREAD_1",
            replyQuery: "mutation Reply",
            replyVariables: { threadId: "THREAD_1", body: "Disposition" },
            resolveQuery: "mutation Resolve",
            resolveVariables: { threadId: "THREAD_1" },
          },
        ],
      },
      null,
      2
    )}\n`
  );

  await assert.rejects(
    () =>
      executeManifestThreads({
        manifestPath,
        execute: false,
        acceptanceReportPath: "artifacts/acceptance.txt",
      }),
    /requires both --execute and --doc/
  );
});

test("formatExecutionReport renders thread-level dry-run details", () => {
  const report = formatExecutionReport(
    {
      manifestPath: "/tmp/manifest.json",
      execute: false,
      threadCount: 1,
      results: [
        {
          threadNumber: 1,
          manifestThreadNumber: 2,
          threadId: "THREAD_2",
          originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r2",
          location: "src/file.js:20",
          scriptPath: "/tmp/thread-2.sh",
          mode: "dry-run",
          replyCommand: "gh api graphql -f query=reply",
          resolveCommand: "gh api graphql -f query=resolve",
          replyExitStatus: null,
          resolveExitStatus: null,
          replyOutput: null,
          resolveOutput: null,
        },
      ],
    }
  );

  assert.match(report, /# Disposition Thread Dry Run/);
  assert.match(report, /## Thread 1 \(Manifest Thread 2\): THREAD_2/);
  assert.match(report, /- Script Path: `\/tmp\/thread-2\.sh`/);
  assert.match(report, /- Reply Command: `gh api graphql -f query=reply`/);
  assert.match(report, /- Resolve Command: `gh api graphql -f query=resolve`/);
});

test("formatExecutionReport renders inventory update details when present", () => {
  const report = formatExecutionReport(
    {
      manifestPath: "/tmp/manifest.json",
      execute: true,
      threadCount: 1,
      inventoryUpdate: {
        docPath: "/tmp/pr-178-unresolved-threads.md",
        resolvedThreadCount: 1,
        remainingThreadCount: 0,
      },
      results: [
        {
          threadNumber: 1,
          manifestThreadNumber: 1,
          threadId: "THREAD_1",
          originalThreadUrl: null,
          location: null,
          scriptPath: null,
          mode: "execute",
          replyCommand: "gh api graphql -f query=reply",
          resolveCommand: "gh api graphql -f query=resolve",
          replyExitStatus: 0,
          resolveExitStatus: 0,
          replyOutput: "ok",
          resolveOutput: "ok",
        },
      ],
    }
  );

  assert.match(report, /Inventory Doc Updated: `\/tmp\/pr-178-unresolved-threads\.md`/);
  assert.match(report, /Resolved Threads Moved: 1/);
  assert.match(report, /Remaining Active Threads: 0/);
});
