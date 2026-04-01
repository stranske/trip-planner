#!/usr/bin/env node

"use strict";

const path = require("node:path");

const {
  collectThreadInventoryIssues,
  DEFAULT_DOC_PATH,
  loadThreadInventory,
} = require("./list_fix_threads_from_doc.js");

const ADD_PULL_REQUEST_REVIEW_THREAD_REPLY_MUTATION = [
  "mutation AddPullRequestReviewThreadReply($threadId: ID!, $body: String!) {",
  "  addPullRequestReviewThreadReply(",
  "    input: { pullRequestReviewThreadId: $threadId, body: $body }",
  "  ) {",
  "    comment {",
  "      url",
  "    }",
  "  }",
  "}",
].join("\n");

const RESOLVE_REVIEW_THREAD_MUTATION = [
  "mutation ResolveReviewThread($threadId: ID!) {",
  "  resolveReviewThread(input: { threadId: $threadId }) {",
  "    thread {",
  "      isResolved",
  "    }",
  "  }",
  "}",
].join("\n");

function listDispositionClassifiedThreads(threads, options = {}) {
  const { excludeOutdated = false } = options;
  const dispositionThreads = threads.filter((thread) => thread.classification === "disposition");

  if (!excludeOutdated) {
    return dispositionThreads;
  }

  return dispositionThreads.filter((thread) => thread.outdated !== true);
}

function formatDispositionThreadsReport(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = [`Disposition-classified threads: ${dispositionThreads.length}`];

  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated disposition threads: ${excludedOutdatedCount}`);
  }

  if (dispositionThreads.length === 0) {
    return `${lines.join("\n")}\n`;
  }

  dispositionThreads.forEach((thread, index) => {
    lines.push(`${index + 1}. ${thread.threadId || "<missing thread id>"}`);
    lines.push(`   Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`   Location: ${thread.location || "<missing location>"}`);
    lines.push(`   Rationale: ${thread.rationale || "<missing rationale>"}`);
    lines.push(`   Content: ${thread.content || "<missing content>"}`);
    lines.push(
      `   Outdated: ${
        thread.outdated === null
          ? "<missing outdated status>"
          : thread.outdated
            ? "yes"
            : "no"
      }`
    );
  });

  return `${lines.join("\n")}\n`;
}

function formatDispositionThreadsAsJson(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  return `${JSON.stringify(
    {
      dispositionThreads,
      count: dispositionThreads.length,
      excludedOutdatedCount,
    },
    null,
    2
  )}\n`;
}

function formatDispositionThreadsAsMarkdown(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = ["# Disposition Thread Scope", ""];

  lines.push(`Disposition-classified threads: ${dispositionThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated disposition threads: ${excludedOutdatedCount}`);
  }

  if (dispositionThreads.length === 0) {
    lines.push("", "No disposition-classified threads found.");
    return `${lines.join("\n")}\n`;
  }

  dispositionThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(`## Disposition Thread ${index + 1}`);
    lines.push("");
    lines.push(`- [ ] Post disposition for \`${thread.threadId || "<missing thread id>"}\``);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${thread.location || "<missing location>"}`);
    lines.push(`- Rationale: ${thread.rationale || "<missing rationale>"}`);
    lines.push(`- Content: ${thread.content || "<missing content>"}`);
    lines.push(
      `- Outdated: ${
        thread.outdated === null
          ? "<missing outdated status>"
          : thread.outdated
            ? "yes"
            : "no"
      }`
    );
  });

  return `${lines.join("\n")}\n`;
}

function formatDispositionThreadsAsPlan(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = ["# Disposition Comment Plan", ""];

  lines.push(`Actionable disposition threads: ${dispositionThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated disposition threads: ${excludedOutdatedCount}`);
  }

  if (dispositionThreads.length === 0) {
    lines.push("", "No actionable disposition threads found.");
    return `${lines.join("\n")}\n`;
  }

  dispositionThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(`## Disposition Thread ${index + 1}`);
    lines.push("");
    lines.push(`- Thread: ${thread.threadId || "<missing thread id>"}`);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${thread.location || "<missing location>"}`);
    lines.push(`- Rationale to post: ${thread.rationale || "<missing rationale>"}`);
    lines.push(`- Supporting review context: ${thread.content || "<missing content>"}`);
    lines.push("- Next Step: Reply on PR #178 with the disposition rationale and resolve the thread.");
  });

  return `${lines.join("\n")}\n`;
}

function formatDispositionThreadsAsComments(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = ["# Disposition Comment Drafts", ""];

  lines.push(`Actionable disposition threads: ${dispositionThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated disposition threads: ${excludedOutdatedCount}`);
  }

  if (dispositionThreads.length === 0) {
    lines.push("", "No actionable disposition threads found.");
    return `${lines.join("\n")}\n`;
  }

  dispositionThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(`## Disposition Thread ${index + 1}`);
    lines.push("");
    lines.push(`- Thread: ${thread.threadId || "<missing thread id>"}`);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${thread.location || "<missing location>"}`);
    lines.push("");
    lines.push("```markdown");
    lines.push(thread.rationale || "<missing rationale>");

    if (thread.content) {
      lines.push("");
      lines.push(`Context from unresolved thread: ${thread.content}`);
    }

    lines.push("```");
  });

  return `${lines.join("\n")}\n`;
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function buildDispositionReplyBody(thread) {
  const lines = [thread.rationale || "<missing rationale>"];

  if (thread.content) {
    lines.push("", `Context from unresolved thread: ${thread.content}`);
  }

  return lines.join("\n");
}

function formatDispositionThreadsAsGhCli(dispositionThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = ["# Disposition Thread gh CLI Commands", ""];

  lines.push(`Actionable disposition threads: ${dispositionThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated disposition threads: ${excludedOutdatedCount}`);
  }

  if (dispositionThreads.length === 0) {
    lines.push("", "No actionable disposition threads found.");
    return `${lines.join("\n")}\n`;
  }

  dispositionThreads.forEach((thread, index) => {
    const threadId = thread.threadId || "<missing thread id>";
    const replyBody = buildDispositionReplyBody(thread);
    const replyCommand = [
      "gh",
      "api",
      "graphql",
      "-f",
      `query=${shellQuote(ADD_PULL_REQUEST_REVIEW_THREAD_REPLY_MUTATION)}`,
      "-F",
      `threadId=${shellQuote(threadId)}`,
      "-F",
      `body=${shellQuote(replyBody)}`,
    ].join(" ");
    const resolveCommand = [
      "gh",
      "api",
      "graphql",
      "-f",
      `query=${shellQuote(RESOLVE_REVIEW_THREAD_MUTATION)}`,
      "-F",
      `threadId=${shellQuote(threadId)}`,
    ].join(" ");

    lines.push("");
    lines.push(`## Disposition Thread ${index + 1}`);
    lines.push("");
    lines.push(`- Thread: ${threadId}`);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${thread.location || "<missing location>"}`);
    lines.push("");
    lines.push("```bash");
    lines.push(replyCommand);
    lines.push(resolveCommand);
    lines.push("```");
  });

  return `${lines.join("\n")}\n`;
}

function formatDispositionThreadsOutput(dispositionThreads, outputFormat = "text", options = {}) {
  if (outputFormat === "json") {
    return formatDispositionThreadsAsJson(dispositionThreads, options);
  }

  if (outputFormat === "markdown") {
    return formatDispositionThreadsAsMarkdown(dispositionThreads, options);
  }

  if (outputFormat === "plan") {
    return formatDispositionThreadsAsPlan(dispositionThreads, options);
  }

  if (outputFormat === "comments") {
    return formatDispositionThreadsAsComments(dispositionThreads, options);
  }

  if (outputFormat === "gh-cli") {
    return formatDispositionThreadsAsGhCli(dispositionThreads, options);
  }

  return formatDispositionThreadsReport(dispositionThreads, options);
}

function buildDispositionThreadsReport(options = {}, dependencies = {}) {
  const {
    docPath = DEFAULT_DOC_PATH,
    excludeOutdated = false,
    outputFormat = "text",
    requireComplete = false,
  } = options;
  const loadInventory = dependencies.loadThreadInventory || loadThreadInventory;
  const threads = loadInventory(docPath, dependencies);
  const activeThreads = loadInventory(docPath, dependencies, {
    inventorySection: "unresolved",
  });
  const issues = collectThreadInventoryIssues(threads);

  if (requireComplete && issues.length > 0) {
    throw new Error(issues.join("\n"));
  }

  const allDispositionThreads = listDispositionClassifiedThreads(activeThreads);
  const actionableDispositionThreads = listDispositionClassifiedThreads(activeThreads, {
    excludeOutdated,
  });
  const excludedOutdatedCount = allDispositionThreads.length - actionableDispositionThreads.length;

  return formatDispositionThreadsOutput(actionableDispositionThreads, outputFormat, {
    excludedOutdatedCount,
  });
}

function getCliConfiguration(argv = process.argv.slice(2)) {
  const options = {
    docPath: DEFAULT_DOC_PATH,
    excludeOutdated: false,
    outputFormat: "text",
    requireComplete: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--require-complete") {
      options.requireComplete = true;
      continue;
    }

    if (argument === "--exclude-outdated") {
      options.excludeOutdated = true;
      continue;
    }

    if (argument === "--format") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --format flag requires a value.");
      }

      options.outputFormat = value;
      index += 1;
      continue;
    }

    if (argument.startsWith("--")) {
      throw new Error(`Unknown option: ${argument}`);
    }

    if (options.docPath !== DEFAULT_DOC_PATH) {
      throw new Error(`Unexpected argument: ${argument}`);
    }

    options.docPath = path.resolve(argument);
  }

  if (!["text", "json", "markdown", "plan", "comments", "gh-cli"].includes(options.outputFormat)) {
    throw new Error(
      `Output format must be one of "text", "json", "markdown", "plan", "comments", or "gh-cli"; received "${options.outputFormat}".`
    );
  }

  return options;
}

function main(argv = process.argv.slice(2)) {
  const { docPath, excludeOutdated, outputFormat, requireComplete } = getCliConfiguration(argv);
  process.stdout.write(
    buildDispositionThreadsReport({ docPath, excludeOutdated, outputFormat, requireComplete })
  );
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = {
  buildDispositionThreadsReport,
  formatDispositionThreadsAsJson,
  formatDispositionThreadsAsMarkdown,
  formatDispositionThreadsAsPlan,
  formatDispositionThreadsAsComments,
  formatDispositionThreadsAsGhCli,
  formatDispositionThreadsOutput,
  formatDispositionThreadsReport,
  getCliConfiguration,
  listDispositionClassifiedThreads,
  buildDispositionReplyBody,
};
