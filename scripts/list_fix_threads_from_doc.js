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
      location: null,
      classification: null,
      rationale: null,
      content: null,
    };

    section
      .split("\n")
      .map((line) => line.trim())
      .forEach((line) => {
        if (line.startsWith("- Thread ID:")) {
          thread.threadId = normalizeFieldValue(line.slice("- Thread ID:".length));
        } else if (line.startsWith("- Location:")) {
          thread.location = normalizeFieldValue(line.slice("- Location:".length));
        } else if (line.startsWith("- Classification:")) {
          const classification = normalizeFieldValue(line.slice("- Classification:".length));
          thread.classification = classification ? classification.toLowerCase() : null;
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
    lines.push(`   Location: ${thread.location || "<missing location>"}`);
    lines.push(`   Rationale: ${thread.rationale || "<missing rationale>"}`);
    lines.push(`   Content: ${thread.content || "<missing content>"}`);
  });

  return `${lines.join("\n")}\n`;
}

function main(argv = process.argv.slice(2)) {
  const docPath = argv[0] ? path.resolve(argv[0]) : DEFAULT_DOC_PATH;
  const threads = loadThreadInventory(docPath);
  const fixThreads = listFixClassifiedThreads(threads);
  process.stdout.write(formatFixThreadsReport(fixThreads));
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
  DEFAULT_DOC_PATH,
  formatFixThreadsReport,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeFieldValue,
  parseThreadInventory,
};
