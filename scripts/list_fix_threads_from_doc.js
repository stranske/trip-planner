#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_DOC_PATH = path.resolve(__dirname, "..", "docs", "pr-178-unresolved-threads.md");

function parseThreadInventory(markdown) {
  const sections = markdown.split(/^###\s+Thread\s+\d+\s*$/m).slice(1);

  return sections.map((section) => {
    const thread = {
      threadId: null,
      originalThreadUrl: null,
      location: null,
      classification: null,
      followUpPr: null,
      rationale: null,
      content: null,
    };

    section
      .split("\n")
      .map((line) => line.trim())
      .forEach((line) => {
        if (line.startsWith("- Thread ID:")) {
          thread.threadId = normalizeFieldValue(line.slice("- Thread ID:".length));
        } else if (line.startsWith("- Original Thread URL:")) {
          thread.originalThreadUrl = normalizeFieldValue(
            line.slice("- Original Thread URL:".length)
          );
        } else if (line.startsWith("- Location:")) {
          thread.location = normalizeFieldValue(line.slice("- Location:".length));
        } else if (line.startsWith("- Classification:")) {
          const classification = normalizeFieldValue(line.slice("- Classification:".length));
          thread.classification = classification ? classification.toLowerCase() : null;
        } else if (line.startsWith("- Follow-up PR:")) {
          thread.followUpPr = normalizeFieldValue(line.slice("- Follow-up PR:".length));
        } else if (line.startsWith("- Rationale:")) {
          thread.rationale = normalizeFieldValue(line.slice("- Rationale:".length));
        } else if (line.startsWith("- Content:")) {
          thread.content = normalizeFieldValue(line.slice("- Content:".length));
        }
      });

    return thread;
  });
}

function normalizeFieldValue(value) {
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
}

function collectThreadInventoryIssues(threads) {
  const issues = [];

  threads.forEach((thread, index) => {
    const threadLabel = thread.threadId || `Thread ${index + 1}`;

    if (!thread.threadId) {
      issues.push(`${threadLabel}: missing thread ID`);
    }

    if (!thread.originalThreadUrl) {
      issues.push(`${threadLabel}: missing original thread URL`);
    }

    if (!thread.location) {
      issues.push(`${threadLabel}: missing location`);
    }

    if (!thread.classification) {
      issues.push(`${threadLabel}: missing classification`);
    } else if (!["fix", "disposition"].includes(thread.classification)) {
      issues.push(`${threadLabel}: invalid classification "${thread.classification}"`);
    } else if (thread.classification === "fix" && !thread.followUpPr) {
      issues.push(`${threadLabel}: missing follow-up PR`);
    }

    if (!thread.rationale) {
      issues.push(`${threadLabel}: missing rationale`);
    }

    if (!thread.content) {
      issues.push(`${threadLabel}: missing content`);
    }
  });

  return issues;
}

function formatThreadInventoryIssues(issues) {
  if (issues.length === 0) {
    return "Thread inventory is complete.\n";
  }

  const lines = [`Thread inventory issues: ${issues.length}`];
  issues.forEach((issue, index) => {
    lines.push(`${index + 1}. ${issue}`);
  });
  return `${lines.join("\n")}\n`;
}

function loadThreadInventory(docPath = DEFAULT_DOC_PATH, dependencies = {}) {
  const readFileSync = dependencies.readFileSync || fs.readFileSync;
  return parseThreadInventory(readFileSync(docPath, "utf8"));
}

function listFixClassifiedThreads(threads) {
  return threads.filter((thread) => thread.classification === "fix");
}

function formatFixThreadsReport(fixThreads) {
  if (fixThreads.length === 0) {
    return "Fix-classified threads: 0\n";
  }

  const lines = [`Fix-classified threads: ${fixThreads.length}`];
  fixThreads.forEach((thread, index) => {
    lines.push(`${index + 1}. ${thread.threadId || "<missing thread id>"}`);
    lines.push(`   Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`   Location: ${thread.location || "<missing location>"}`);
    lines.push(`   Follow-up PR: ${thread.followUpPr || "<missing follow-up PR>"}`);
    lines.push(`   Rationale: ${thread.rationale || "<missing rationale>"}`);
    lines.push(`   Content: ${thread.content || "<missing content>"}`);
  });

  return `${lines.join("\n")}\n`;
}

function buildFixThreadsReport(options = {}, dependencies = {}) {
  const { docPath = DEFAULT_DOC_PATH, requireComplete = false } = options;
  const threads = loadThreadInventory(docPath, dependencies);
  const issues = collectThreadInventoryIssues(threads);

  if (requireComplete && issues.length > 0) {
    throw new Error(formatThreadInventoryIssues(issues).trimEnd());
  }

  const fixThreads = listFixClassifiedThreads(threads);
  return formatFixThreadsReport(fixThreads);
}

function getCliConfiguration(argv = process.argv.slice(2)) {
  const options = {
    docPath: DEFAULT_DOC_PATH,
    requireComplete: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--require-complete") {
      options.requireComplete = true;
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

  return options;
}

function main(argv = process.argv.slice(2)) {
  const { docPath, requireComplete } = getCliConfiguration(argv);
  process.stdout.write(buildFixThreadsReport({ docPath, requireComplete }));
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
  buildFixThreadsReport,
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeFieldValue,
  parseThreadInventory,
};
