import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildDispositionThreadsReport,
  buildDispositionGhCliCommands,
  buildDispositionReplyBody,
  DEFAULT_ARTIFACTS_DIR,
  formatDispositionThreadsAsComments,
  formatDispositionThreadsAsGhCli,
  formatDispositionThreadsAsJson,
  formatDispositionThreadsAsMarkdown,
  formatDispositionThreadsAsPlan,
  formatDispositionThreadsReport,
  formatDispositionThreadsOutput,
  getCliConfiguration,
  listDispositionClassifiedThreads,
  writeDispositionArtifacts,
} = require(path.join(repoRoot, "scripts/list_disposition_threads_from_doc.js"));

test("listDispositionClassifiedThreads returns only disposition entries", () => {
  const threads = listDispositionClassifiedThreads([
    { threadId: "THREAD_1", classification: "fix", outdated: false },
    { threadId: "THREAD_2", classification: "disposition", outdated: false },
    { threadId: "THREAD_3", classification: "disposition", outdated: true },
  ]);

  assert.deepEqual(threads, [
    { threadId: "THREAD_2", classification: "disposition", outdated: false },
    { threadId: "THREAD_3", classification: "disposition", outdated: true },
  ]);
});

test("listDispositionClassifiedThreads can exclude outdated disposition entries", () => {
  const threads = listDispositionClassifiedThreads(
    [
      { threadId: "THREAD_1", classification: "disposition", outdated: false },
      { threadId: "THREAD_2", classification: "disposition", outdated: true },
      { threadId: "THREAD_3", classification: "fix", outdated: false },
    ],
    { excludeOutdated: true }
  );

  assert.deepEqual(threads, [
    { threadId: "THREAD_1", classification: "disposition", outdated: false },
  ]);
});

test("formatDispositionThreadsReport renders thread metadata", () => {
  const report = formatDispositionThreadsReport([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
      outdated: false,
    },
  ]);

  assert.match(report, /Disposition-classified threads: 1/);
  assert.match(report, /THREAD_1/);
  assert.match(report, /Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/);
  assert.match(report, /Rationale: The existing behavior is intentional\./);
});

test("formatDispositionThreadsAsMarkdown emits a checklist for posting disposition comments", () => {
  const report = formatDispositionThreadsAsMarkdown([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Disposition Thread Scope/);
  assert.match(report, /- \[ \] Post disposition for `THREAD_1`/);
  assert.match(report, /- Original Thread URL: https:\/\/github\.com\/stranske\/trip-planner\/pull\/178#discussion_r1/);
});

test("formatDispositionThreadsAsPlan emits resolution steps for PR comments", () => {
  const report = formatDispositionThreadsAsPlan([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Disposition Comment Plan/);
  assert.match(report, /Actionable disposition threads: 1/);
  assert.match(report, /Next Step: Reply on PR #178 with the disposition rationale and resolve the thread\./);
});

test("formatDispositionThreadsAsComments emits ready-to-post disposition comment drafts", () => {
  const report = formatDispositionThreadsAsComments([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Disposition Comment Drafts/);
  assert.match(report, /- Thread: THREAD_1/);
  assert.match(report, /```markdown/);
  assert.match(report, /The existing behavior is intentional\./);
  assert.match(report, /Context from unresolved thread: reviewer: Please change the template wording\./);
});

test("buildDispositionReplyBody combines rationale with thread context", () => {
  assert.equal(
    buildDispositionReplyBody({
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
    }),
    [
      "The existing behavior is intentional.",
      "",
      "Context from unresolved thread: reviewer: Please change the template wording.",
    ].join("\n")
  );
});

test("buildDispositionGhCliCommands returns paired reply and resolve commands", () => {
  const commands = buildDispositionGhCliCommands({
    threadId: "THREAD_1",
    rationale: "The existing behavior is intentional.",
    content: "reviewer: Please change the template wording.",
  });

  assert.equal(commands.threadId, "THREAD_1");
  assert.match(commands.replyCommand, /mutation AddPullRequestReviewThreadReply/);
  assert.match(commands.replyCommand, /-F threadId='THREAD_1'/);
  assert.match(commands.resolveCommand, /mutation ResolveReviewThread/);
  assert.match(commands.resolveCommand, /-F threadId='THREAD_1'/);
});

test("formatDispositionThreadsAsGhCli emits reply and resolve commands", () => {
  const report = formatDispositionThreadsAsGhCli([
    {
      threadId: "THREAD_1",
      originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
      location: "docs/pr-178-unresolved-threads.md:12",
      rationale: "The existing behavior is intentional.",
      content: "reviewer: Please change the template wording.",
      outdated: false,
    },
  ]);

  assert.match(report, /# Disposition Thread gh CLI Commands/);
  assert.match(report, /Actionable disposition threads: 1/);
  assert.match(report, /- Thread: THREAD_1/);
  assert.match(report, /gh api graphql -f query='mutation AddPullRequestReviewThreadReply/);
  assert.match(report, /-F threadId='THREAD_1'/);
  assert.match(report, /-F body='The existing behavior is intentional\./);
  assert.match(report, /Context from unresolved thread: reviewer: Please change the template wording\.'/);
  assert.match(report, /gh api graphql -f query='mutation ResolveReviewThread/);
});

test("writeDispositionArtifacts writes executable scripts and a manifest", () => {
  const artifactsDir = fs.mkdtempSync(path.join(os.tmpdir(), "disposition-artifacts-"));
  const artifactInfo = writeDispositionArtifacts(
    [
      {
        threadId: "THREAD_1",
        originalThreadUrl: "https://github.com/stranske/trip-planner/pull/178#discussion_r1",
        location: "docs/pr-178-unresolved-threads.md:12",
        rationale: "The existing behavior is intentional.",
        content: "reviewer: Please change the template wording.",
      },
    ],
    artifactsDir
  );

  const manifest = JSON.parse(fs.readFileSync(artifactInfo.manifestPath, "utf8"));

  assert.equal(manifest.count, 1);
  assert.equal(manifest.expectDocCount, 1);
  assert.equal(manifest.threads[0].threadId, "THREAD_1");
  assert.match(manifest.threads[0].scriptPath, /pr-178-disposition-thread-1-thread-1-resolve\.sh$/);
  const scriptBody = fs.readFileSync(manifest.threads[0].scriptPath, "utf8");
  assert.match(scriptBody, /set -euo pipefail/);
  assert.match(scriptBody, /mutation AddPullRequestReviewThreadReply/);
  assert.match(scriptBody, /mutation ResolveReviewThread/);
});

test("formatDispositionThreadsAsJson includes the excluded outdated count", () => {
  const report = formatDispositionThreadsAsJson(
    [{ threadId: "THREAD_1", classification: "disposition", outdated: false }],
    { excludedOutdatedCount: 2 }
  );
  const parsed = JSON.parse(report);

  assert.equal(parsed.count, 1);
  assert.equal(parsed.excludedOutdatedCount, 2);
});

test("formatDispositionThreadsOutput dispatches to the requested formatter", () => {
  const jsonReport = formatDispositionThreadsOutput([], "json");
  assert.equal(JSON.parse(jsonReport).count, 0);

  const markdownReport = formatDispositionThreadsOutput([], "markdown");
  assert.match(markdownReport, /No disposition-classified threads found\./);

  const planReport = formatDispositionThreadsOutput([], "plan");
  assert.match(planReport, /No actionable disposition threads found\./);

  const commentsReport = formatDispositionThreadsOutput([], "comments");
  assert.match(commentsReport, /No actionable disposition threads found\./);

  const ghCliReport = formatDispositionThreadsOutput([], "gh-cli");
  assert.match(ghCliReport, /No actionable disposition threads found\./);
});

test("buildDispositionThreadsReport filters unresolved disposition threads from the inventory", () => {
  const report = buildDispositionThreadsReport(
    {
      docPath: "/tmp/inventory.md",
      excludeOutdated: true,
      outputFormat: "json",
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) => {
        if (options.inventorySection === "unresolved") {
          return [
            {
              threadId: "THREAD_1",
              classification: "disposition",
              outdated: false,
              originalThreadUrl: "https://github.com/example/repo/pull/178#discussion_r1",
              location: "src/file.js:10",
              rationale: "Still intentional.",
              content: "reviewer: Clarify this.",
            },
            {
              threadId: "THREAD_2",
              classification: "disposition",
              outdated: true,
              originalThreadUrl: "https://github.com/example/repo/pull/178#discussion_r2",
              location: "src/file.js:20",
              rationale: "Historical only.",
              content: "reviewer: Old thread.",
            },
            {
              threadId: "THREAD_3",
              classification: "fix",
              outdated: false,
            },
          ];
        }

        return [
          {
            threadId: "THREAD_1",
            classification: "disposition",
            outdated: false,
            originalThreadUrl: "https://github.com/example/repo/pull/178#discussion_r1",
            location: "src/file.js:10",
            rationale: "Still intentional.",
            content: "reviewer: Clarify this.",
          },
        ];
      },
    }
  );
  const parsed = JSON.parse(report);

  assert.equal(parsed.count, 1);
  assert.equal(parsed.excludedOutdatedCount, 1);
  assert.equal(parsed.dispositionThreads[0].threadId, "THREAD_1");
});

test("buildDispositionThreadsReport can write gh-cli artifacts for actionable disposition threads", () => {
  const artifactsDir = fs.mkdtempSync(path.join(os.tmpdir(), "disposition-report-artifacts-"));
  const report = buildDispositionThreadsReport(
    {
      docPath: "/tmp/inventory.md",
      excludeOutdated: true,
      outputFormat: "gh-cli",
      writeArtifactsDir: artifactsDir,
    },
    {
      loadThreadInventory: (_docPath, _dependencies, options = {}) => {
        if (options.inventorySection === "unresolved") {
          return [
            {
              threadId: "THREAD_1",
              classification: "disposition",
              outdated: false,
              originalThreadUrl: "https://github.com/example/repo/pull/178#discussion_r1",
              location: "src/file.js:10",
              rationale: "Still intentional.",
              content: "reviewer: Clarify this.",
            },
          ];
        }

        return [
          {
            threadId: "THREAD_1",
            classification: "disposition",
            outdated: false,
            originalThreadUrl: "https://github.com/example/repo/pull/178#discussion_r1",
            location: "src/file.js:10",
            rationale: "Still intentional.",
            content: "reviewer: Clarify this.",
          },
        ];
      },
    }
  );

  assert.match(report, /Artifacts directory:/);
  assert.match(report, /Manifest:/);
  const manifestPath = path.join(artifactsDir, "manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.count, 1);
  assert.equal(manifest.expectDocCount, 1);
});

test("buildDispositionThreadsReport can require a complete inventory", () => {
  assert.throws(
    () =>
      buildDispositionThreadsReport(
        {
          docPath: "/tmp/inventory.md",
          requireComplete: true,
        },
        {
          loadThreadInventory: () => [
            {
              threadId: "THREAD_1",
              classification: "disposition",
              outdated: false,
              originalThreadUrl: null,
              location: null,
              rationale: null,
              content: null,
            },
          ],
        }
      ),
    /missing original thread URL/
  );
});

test("getCliConfiguration parses completeness validation, doc path, and output format", () => {
  assert.deepEqual(
    getCliConfiguration([
      "--require-complete",
      "--exclude-outdated",
      "--format",
      "gh-cli",
      "--write-artifacts-dir",
      ".tmp/disposition",
      "docs/pr-178-unresolved-threads.md",
    ]),
    {
      docPath: path.resolve("docs/pr-178-unresolved-threads.md"),
      excludeOutdated: true,
      outputFormat: "gh-cli",
      requireComplete: true,
      writeArtifactsDir: path.resolve(".tmp/disposition"),
    }
  );
});

test("getCliConfiguration rejects unknown options and extra positional arguments", () => {
  assert.throws(() => getCliConfiguration(["--unknown"]), /Unknown option: --unknown/);
  assert.throws(
    () => getCliConfiguration(["--format", "html"]),
    /Output format must be one of "text", "json", "markdown", "plan", "comments", or "gh-cli"/
  );
  assert.throws(
    () => getCliConfiguration(["docs/one.md", "docs/two.md"]),
    /Unexpected argument: docs\/two\.md/
  );
  assert.throws(
    () => getCliConfiguration(["--write-artifacts-dir", DEFAULT_ARTIFACTS_DIR]),
    /requires "--format gh-cli"/
  );
});
