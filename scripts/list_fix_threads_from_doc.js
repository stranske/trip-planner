#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_DOC_PATH = path.resolve(__dirname, "..", "docs", "pr-178-unresolved-threads.md");
const PLACEHOLDER_VALUES = new Set(["tbd", "todo", "pending", "unknown"]);

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
      outdated: null,
    };

    let currentField = null;

    section.split("\n").forEach((rawLine) => {
      const line = rawLine.trim();

      if (line === "") {
        currentField = null;
        return;
      }

      if (line.startsWith("- Thread ID:")) {
        thread.threadId = normalizeFieldValue(line.slice("- Thread ID:".length));
        currentField = "threadId";
      } else if (line.startsWith("- Original Thread URL:")) {
        thread.originalThreadUrl = normalizeUrlFieldValue(line.slice("- Original Thread URL:".length));
        currentField = "originalThreadUrl";
      } else if (line.startsWith("- Location:")) {
        thread.location = normalizeFieldValue(line.slice("- Location:".length));
        currentField = "location";
      } else if (line.startsWith("- Classification:")) {
        const classification = normalizeFieldValue(line.slice("- Classification:".length));
        thread.classification = classification ? classification.toLowerCase() : null;
        currentField = "classification";
      } else if (line.startsWith("- Follow-up PR:")) {
        thread.followUpPr = normalizeUrlFieldValue(line.slice("- Follow-up PR:".length));
        currentField = "followUpPr";
      } else if (line.startsWith("- Rationale:")) {
        thread.rationale = normalizeFieldValue(line.slice("- Rationale:".length));
        currentField = "rationale";
      } else if (line.startsWith("- Content:")) {
        thread.content = normalizeFieldValue(line.slice("- Content:".length));
        currentField = "content";
      } else if (line.startsWith("- Outdated:")) {
        thread.outdated = normalizeOutdatedFieldValue(line.slice("- Outdated:".length));
        currentField = "outdated";
      } else if (currentField) {
        appendContinuationLine(thread, currentField, line);
      }
    });

    return thread;
  });
}

function appendContinuationLine(thread, fieldName, line) {
  const currentValue = thread[fieldName];
  const joinedValue = [currentValue, line].filter(Boolean).join(" ");

  if (fieldName === "classification") {
    thread.classification = normalizeFieldValue(joinedValue)?.toLowerCase() || null;
    return;
  }

  if (fieldName === "originalThreadUrl" || fieldName === "followUpPr") {
    thread[fieldName] = normalizeUrlFieldValue(joinedValue);
    return;
  }

  if (fieldName === "outdated") {
    thread.outdated = normalizeOutdatedFieldValue(joinedValue);
    return;
  }

  thread[fieldName] = normalizeFieldValue(joinedValue);
}

function normalizeFieldValue(value) {
  const normalized = value.trim();
  if (normalized === "") {
    return null;
  }

  return isPlaceholderValue(normalized) ? null : normalized;
}

function normalizeUrlFieldValue(value) {
  const normalized = normalizeFieldValue(value);
  if (!normalized) {
    return null;
  }

  const markdownLinkMatch = normalized.match(/^\[[^\]]+\]\((https?:\/\/[^)\s]+)\)$/i);
  if (markdownLinkMatch) {
    return markdownLinkMatch[1];
  }

  const autoLinkMatch = normalized.match(/^<(https?:\/\/[^>\s]+)>$/i);
  if (autoLinkMatch) {
    return autoLinkMatch[1];
  }

  return normalized;
}

function normalizeOutdatedFieldValue(value) {
  const normalized = normalizeFieldValue(value);
  if (!normalized) {
    return null;
  }

  if (normalized === "yes") {
    return true;
  }

  if (normalized === "no") {
    return false;
  }

  return normalized;
}

function isPlaceholderValue(value) {
  return PLACEHOLDER_VALUES.has(value.trim().toLowerCase());
}

function collectThreadInventoryIssues(threads) {
  const issues = [];
  const seenThreadIds = new Map();
  const seenOriginalThreadUrls = new Map();

  threads.forEach((thread, index) => {
    const threadLabel = thread.threadId || `Thread ${index + 1}`;

    if (!thread.threadId) {
      issues.push(`${threadLabel}: missing thread ID`);
    } else {
      const firstSeenIndex = seenThreadIds.get(thread.threadId);
      if (firstSeenIndex !== undefined) {
        issues.push(
          `${threadLabel}: duplicate thread ID also used by Thread ${firstSeenIndex + 1}`
        );
      } else {
        seenThreadIds.set(thread.threadId, index);
      }
    }

    if (!thread.originalThreadUrl) {
      issues.push(`${threadLabel}: missing original thread URL`);
    } else {
      const firstSeenIndex = seenOriginalThreadUrls.get(thread.originalThreadUrl);
      if (firstSeenIndex !== undefined) {
        issues.push(
          `${threadLabel}: duplicate original thread URL also used by Thread ${firstSeenIndex + 1}`
        );
      } else {
        seenOriginalThreadUrls.set(thread.originalThreadUrl, index);
      }
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

    if (thread.outdated === null) {
      issues.push(`${threadLabel}: missing outdated status`);
    } else if (typeof thread.outdated !== "boolean") {
      issues.push(`${threadLabel}: invalid outdated status "${thread.outdated}"`);
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

function listActionableFixThreads(threads, options = {}) {
  const { excludeOutdated = false } = options;
  const fixThreads = listFixClassifiedThreads(threads);

  if (!excludeOutdated) {
    return fixThreads;
  }

  return fixThreads.filter((thread) => thread.outdated !== true);
}

function sanitizeBranchSegment(value, fallback) {
  const normalized = (value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return normalized || fallback;
}

function buildSuggestedBranchName(thread, index) {
  const locationSegment = sanitizeBranchSegment(thread.location, `thread-${index + 1}`);
  const idSegment = sanitizeBranchSegment(thread.threadId, `thread-${index + 1}`);
  return `pr-178-fix/${locationSegment}-${idSegment}`;
}

function groupFixThreadsByFollowUpPr(fixThreads) {
  const groups = new Map();

  fixThreads.forEach((thread, index) => {
    const followUpPr = thread.followUpPr || null;
    const groupKey = followUpPr || "__missing__";
    const existingGroup = groups.get(groupKey);
    const threadWithBranch = {
      ...thread,
      suggestedBranch: buildSuggestedBranchName(thread, index),
    };

    if (existingGroup) {
      existingGroup.threads.push(threadWithBranch);
      return;
    }

    groups.set(groupKey, {
      followUpPr,
      threadCount: 1,
      threads: [threadWithBranch],
    });
  });

  return Array.from(groups.values()).map((group) => ({
    ...group,
    threadCount: group.threads.length,
  }));
}

function appendFollowUpPrGroupSummary(lines, followUpPrGroups, prefix = "") {
  if (followUpPrGroups.length === 0) {
    return;
  }

  lines.push(`${prefix}Follow-up PR groups: ${followUpPrGroups.length}`);
  followUpPrGroups.forEach((group, groupIndex) => {
    lines.push(
      `${prefix}${groupIndex + 1}. ${group.followUpPr || "<missing follow-up PR>"} (${group.threadCount} thread${group.threadCount === 1 ? "" : "s"})`
    );
    group.threads.forEach((thread) => {
      lines.push(
        `${prefix}   - ${thread.threadId || "<missing thread id>"} -> ${thread.suggestedBranch}`
      );
    });
  });
}

function formatFixThreadsReport(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  if (fixThreads.length === 0) {
    const lines = ["Fix-classified threads: 0"];
    if (excludedOutdatedCount > 0) {
      lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`);
    }
    return `${lines.join("\n")}\n`;
  }

  const lines = [`Fix-classified threads: ${fixThreads.length}`];
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`);
  }
  fixThreads.forEach((thread, index) => {
    lines.push(`${index + 1}. ${thread.threadId || "<missing thread id>"}`);
    lines.push(`   Suggested Branch: ${buildSuggestedBranchName(thread, index)}`);
    lines.push(`   Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`   Location: ${thread.location || "<missing location>"}`);
    lines.push(`   Follow-up PR: ${thread.followUpPr || "<missing follow-up PR>"}`);
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

  lines.push("");
  appendFollowUpPrGroupSummary(lines, followUpPrGroups);

  return `${lines.join("\n")}\n`;
}

function formatFixThreadsAsJson(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  return `${JSON.stringify(
    {
      fixThreads: fixThreads.map((thread, index) => ({
        ...thread,
        suggestedBranch: buildSuggestedBranchName(thread, index),
      })),
      followUpPrGroups,
      count: fixThreads.length,
      excludedOutdatedCount,
    },
    null,
    2
  )}\n`;
}

function formatFixThreadsAsMarkdown(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const lines = ["# Fix-Classified Thread Scope", ""];
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);

  if (fixThreads.length === 0) {
    if (excludedOutdatedCount > 0) {
      lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
    }
    lines.push("No fix-classified threads found.");
    return `${lines.join("\n")}\n`;
  }

  lines.push(`Fix-classified threads: ${fixThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`);
  }

  fixThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(`## Fix Thread ${index + 1}`);
    lines.push("");
    lines.push(`- [ ] Address thread \`${thread.threadId || "<missing thread id>"}\``);
    lines.push(`- Suggested Branch: \`${buildSuggestedBranchName(thread, index)}\``);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${thread.location || "<missing location>"}`);
    lines.push(`- Follow-up PR: ${thread.followUpPr || "<missing follow-up PR>"}`);
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

  lines.push("", "## Follow-up PR Groups", "");
  if (followUpPrGroups.length === 0) {
    lines.push("No follow-up PR groups identified.");
  } else {
    followUpPrGroups.forEach((group, groupIndex) => {
      lines.push(
        `### Follow-up PR Group ${groupIndex + 1}: ${group.followUpPr || "<missing follow-up PR>"}`
      );
      lines.push("");
      lines.push(`- Thread Count: ${group.threadCount}`);
      group.threads.forEach((thread) => {
        lines.push(
          `- [ ] ${thread.threadId || "<missing thread id>"} via \`${thread.suggestedBranch}\``
        );
      });
      lines.push("");
    });
    lines.pop();
  }

  return `${lines.join("\n")}\n`;
}

function formatFixThreadsAsPlan(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  const lines = ["# Follow-up PR Execution Plan", ""];

  if (fixThreads.length === 0) {
    if (excludedOutdatedCount > 0) {
      lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
    }
    lines.push("No actionable fix-classified threads found.");
    return `${lines.join("\n")}\n`;
  }

  lines.push(`Actionable fix threads: ${fixThreads.length}`);
  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`);
  }
  lines.push(`Follow-up PR groups: ${followUpPrGroups.length}`);

  followUpPrGroups.forEach((group, groupIndex) => {
    lines.push("");
    lines.push(
      `## Follow-up PR Group ${groupIndex + 1}: ${group.followUpPr || "<missing follow-up PR>"}`
    );
    lines.push("");
    lines.push(`- Thread Count: ${group.threadCount}`);

    group.threads.forEach((thread) => {
      lines.push(`- Thread: ${thread.threadId || "<missing thread id>"}`);
      lines.push(`- Suggested Branch: \`${thread.suggestedBranch}\``);
      lines.push(`- Location: ${thread.location || "<missing location>"}`);
      lines.push(`- Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
      lines.push(`- Next Step: Implement the requested code change and reply on the follow-up PR.`);
    });
  });

  return `${lines.join("\n")}\n`;
}

function formatFixThreadsOutput(fixThreads, outputFormat = "text", options = {}) {
  if (outputFormat === "json") {
    return formatFixThreadsAsJson(fixThreads, options);
  }

  if (outputFormat === "markdown") {
    return formatFixThreadsAsMarkdown(fixThreads, options);
  }

  if (outputFormat === "plan") {
    return formatFixThreadsAsPlan(fixThreads, options);
  }

  return formatFixThreadsReport(fixThreads, options);
}

function buildFixThreadsReport(options = {}, dependencies = {}) {
  const {
    docPath = DEFAULT_DOC_PATH,
    excludeOutdated = false,
    requireComplete = false,
    outputFormat = "text",
  } = options;
  const threads = loadThreadInventory(docPath, dependencies);
  const issues = collectThreadInventoryIssues(threads);

  if (requireComplete && issues.length > 0) {
    throw new Error(formatThreadInventoryIssues(issues).trimEnd());
  }

  const allFixThreads = listFixClassifiedThreads(threads);
  const fixThreads = listActionableFixThreads(threads, { excludeOutdated });
  const excludedOutdatedCount = allFixThreads.length - fixThreads.length;
  return formatFixThreadsOutput(fixThreads, outputFormat, { excludedOutdatedCount });
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

  if (!["text", "json", "markdown", "plan"].includes(options.outputFormat)) {
    throw new Error(
      `Output format must be one of "text", "json", "markdown", or "plan"; received "${options.outputFormat}".`
    );
  }

  return options;
}

function main(argv = process.argv.slice(2)) {
  const { docPath, excludeOutdated, outputFormat, requireComplete } = getCliConfiguration(argv);
  process.stdout.write(
    buildFixThreadsReport({ docPath, excludeOutdated, outputFormat, requireComplete })
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
  buildFixThreadsReport,
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  formatFixThreadsAsJson,
  formatFixThreadsAsPlan,
  formatFixThreadsAsMarkdown,
  formatFixThreadsOutput,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  buildSuggestedBranchName,
  groupFixThreadsByFollowUpPr,
  listActionableFixThreads,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeFieldValue,
  normalizeOutdatedFieldValue,
  normalizeUrlFieldValue,
  parseThreadInventory,
  isPlaceholderValue,
};
