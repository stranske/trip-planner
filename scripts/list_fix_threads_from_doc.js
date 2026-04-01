#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_DOC_PATH = path.resolve(__dirname, "..", "docs", "pr-178-unresolved-threads.md");
const DEFAULT_REPOSITORY = "stranske/trip-planner";
const GITHUB_PULL_BASE_URL = `https://github.com/${DEFAULT_REPOSITORY}/pull/`;
const DEFAULT_ARTIFACTS_DIR = ".tmp/pr-thread-payloads";
const PLACEHOLDER_VALUES = new Set(["tbd", "todo", "pending", "unknown"]);

function parseThreadInventory(markdown, options = {}) {
  const inventorySection = options.inventorySection || "all";
  if (!["all", "unresolved", "resolved"].includes(inventorySection)) {
    throw new Error(
      `Inventory section must be one of "all", "unresolved", or "resolved"; received "${inventorySection}".`
    );
  }

  const threads = [];
  let currentThread = null;
  let currentField = null;
  let currentSection = "unresolved";

  const shouldIncludeThread = () =>
    inventorySection === "all" || currentSection === inventorySection;

  const pushCurrentThread = () => {
    if (currentThread && shouldIncludeThread() && !isEmptyInventoryThread(currentThread)) {
      threads.push(currentThread);
    }
  };

  markdown.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();

    if (line === "## Thread Inventory") {
      pushCurrentThread();
      currentThread = null;
      currentSection = "unresolved";
      currentField = null;
      return;
    }

    if (line === "## Resolved Thread Inventory") {
      pushCurrentThread();
      currentThread = null;
      currentSection = "resolved";
      currentField = null;
      return;
    }

    if (/^###\s+Thread\s+\d+\s*$/.test(line)) {
      pushCurrentThread();
      currentThread = {
        threadId: null,
        originalThreadUrl: null,
        location: null,
        classification: null,
        followUpPr: null,
        rationale: null,
        content: null,
        outdated: null,
      };
      currentField = null;
      return;
    }

    if (!currentThread) {
      return;
    }

    if (line === "") {
      currentField = null;
      return;
    }

    if (line.startsWith("- Thread ID:")) {
      currentThread.threadId = normalizeFieldValue(line.slice("- Thread ID:".length));
      currentField = "threadId";
    } else if (line.startsWith("- Original Thread URL:")) {
      currentThread.originalThreadUrl = normalizeUrlFieldValue(
        line.slice("- Original Thread URL:".length)
      );
      currentField = "originalThreadUrl";
    } else if (line.startsWith("- Location:")) {
      currentThread.location = normalizeFieldValue(line.slice("- Location:".length));
      currentField = "location";
    } else if (line.startsWith("- Classification:")) {
      const classification = normalizeFieldValue(line.slice("- Classification:".length));
      currentThread.classification = classification ? classification.toLowerCase() : null;
      currentField = "classification";
    } else if (line.startsWith("- Follow-up PR:")) {
      currentThread.followUpPr = normalizeFollowUpPrFieldValue(line.slice("- Follow-up PR:".length));
      currentField = "followUpPr";
    } else if (line.startsWith("- Rationale:")) {
      currentThread.rationale = normalizeFieldValue(line.slice("- Rationale:".length));
      currentField = "rationale";
    } else if (line.startsWith("- Content:")) {
      currentThread.content = normalizeFieldValue(line.slice("- Content:".length));
      currentField = "content";
    } else if (line.startsWith("- Outdated:")) {
      currentThread.outdated = normalizeOutdatedFieldValue(line.slice("- Outdated:".length));
      currentField = "outdated";
    } else if (currentField) {
      appendContinuationLine(currentThread, currentField, line);
    }
  });

  pushCurrentThread();
  return threads;
}

function isEmptyInventoryThread(thread) {
  return Object.values(thread).every((value) => value === null);
}

function appendContinuationLine(thread, fieldName, line) {
  const currentValue = thread[fieldName];
  const joinedValue = [currentValue, line].filter(Boolean).join(" ");

  if (fieldName === "classification") {
    thread.classification = normalizeFieldValue(joinedValue)?.toLowerCase() || null;
    return;
  }

  if (fieldName === "originalThreadUrl" || fieldName === "followUpPr") {
    thread[fieldName] =
      fieldName === "followUpPr"
        ? normalizeFollowUpPrFieldValue(joinedValue)
        : normalizeUrlFieldValue(joinedValue);
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

function normalizeFollowUpPrFieldValue(value) {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = normalizeUrlFieldValue(value);
  if (!normalized) {
    return null;
  }

  const prNumberMatch =
    normalized.match(/^#(\d+)$/) ||
    normalized.match(/^pr\s*#(\d+)$/i) ||
    normalized.match(/^pull\/(\d+)$/i) ||
    normalized.match(/^\/pull\/(\d+)$/i);

  if (prNumberMatch) {
    return `${GITHUB_PULL_BASE_URL}${prNumberMatch[1]}`;
  }

  return normalized;
}

function isValidFollowUpPrLink(followUpPr) {
  if (!followUpPr) {
    return false;
  }

  return /^https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/\d+(?:[/?#][^\s]*)?$/i.test(
    followUpPr
  );
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
    } else if (thread.classification === "fix" && !isValidFollowUpPrLink(thread.followUpPr)) {
      issues.push(`${threadLabel}: invalid follow-up PR "${thread.followUpPr}"`);
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

function loadThreadInventory(docPath = DEFAULT_DOC_PATH, dependencies = {}, options = {}) {
  const readFileSync = dependencies.readFileSync || fs.readFileSync;
  return parseThreadInventory(readFileSync(docPath, "utf8"), options);
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

function extractPullRequestNumber(followUpPr) {
  if (!followUpPr) {
    return null;
  }

  const pullRequestMatch = followUpPr.match(/\/pull\/(\d+)(?:\/|$)/i);
  return pullRequestMatch ? pullRequestMatch[1] : null;
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

function buildPullRequestPayload(group, groupIndex) {
  const pullRequestNumber = extractPullRequestNumber(group.followUpPr);
  const groupLabel = pullRequestNumber ? `#${pullRequestNumber}` : `group ${groupIndex + 1}`;
  const title = `Address PR #178 fix threads for follow-up PR ${groupLabel}`;
  const bodyLines = [
    "## Summary",
    "",
    `- Address ${group.threadCount} fix-classified review thread${group.threadCount === 1 ? "" : "s"} carried from PR #178.`,
    `- Follow-up PR: ${group.followUpPr || "<missing follow-up PR>"}`,
    "",
    "## Original Review Threads",
    "",
  ];

  group.threads.forEach((thread) => {
    bodyLines.push(`- ${thread.threadId || "<missing thread id>"} (${thread.location || "<missing location>"})`);
    bodyLines.push(`  - Original Thread URL: ${thread.originalThreadUrl || "<missing original thread URL>"}`);
    bodyLines.push(`  - Rationale: ${thread.rationale || "<missing rationale>"}`);
    bodyLines.push(`  - Requested Change: ${thread.content || "<missing content>"}`);
  });

  bodyLines.push("", "## Validation", "", "- [ ] Targeted tests added or updated", "- [ ] Review thread reply posted with implementation details");

  return {
    followUpPr: group.followUpPr,
    followUpPrNumber: pullRequestNumber,
    title,
    body: bodyLines.join("\n"),
    threads: group.threads,
  };
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function buildPullRequestCreationCommand(group, groupIndex, options = {}) {
  const payload = buildPullRequestPayload(group, groupIndex);
  const baseBranch = options.baseBranch || "main";
  const bodyFilePath =
    options.bodyFilePath ||
    path.join(DEFAULT_ARTIFACTS_DIR, `pr-178-fix-group-${groupIndex + 1}-body.md`);
  const commandScriptPath =
    options.commandScriptPath ||
    path.join(DEFAULT_ARTIFACTS_DIR, `pr-178-fix-group-${groupIndex + 1}-create.sh`);
  const headBranch =
    options.headBranch ||
    group.threads[0]?.suggestedBranch ||
    buildSuggestedBranchName(group.threads[0] || {}, groupIndex);
  const command = [
    "gh",
    "pr",
    "create",
    "--base",
    shellQuote(baseBranch),
    "--head",
    shellQuote(headBranch),
    "--title",
    shellQuote(payload.title),
    "--body-file",
    shellQuote(bodyFilePath),
  ].join(" ");

  return {
    ...payload,
    baseBranch,
    headBranch,
    bodyFilePath,
    commandScriptPath,
    command,
  };
}

function buildPullRequestCreationScript(group, groupIndex, options = {}) {
  const payload = buildPullRequestCreationCommand(group, groupIndex, options);
  const script = [
    "#!/usr/bin/env bash",
    "set -euo pipefail",
    "",
    payload.command,
    "",
  ].join("\n");

  return {
    ...payload,
    script,
  };
}

function buildPullRequestArtifactManifest(fixThreads, options = {}) {
  const { baseBranch = "main", artifactsDir = DEFAULT_ARTIFACTS_DIR } = options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  const manifest = {
    artifactsDir,
    baseBranch,
    groups: followUpPrGroups.map((group, groupIndex) =>
      buildPullRequestCreationCommand(group, groupIndex, {
        baseBranch,
        bodyFilePath: path.join(
          artifactsDir,
          `pr-178-fix-group-${groupIndex + 1}-body.md`
        ),
        commandScriptPath: path.join(
          artifactsDir,
          `pr-178-fix-group-${groupIndex + 1}-create.sh`
        ),
      })
    ),
  };

  manifest.manifestPath = path.join(artifactsDir, "manifest.json");
  return manifest;
}

function writePullRequestArtifacts(fixThreads, options = {}, dependencies = {}) {
  const mkdirSync = dependencies.mkdirSync || fs.mkdirSync;
  const writeFileSync = dependencies.writeFileSync || fs.writeFileSync;
  const chmodSync = dependencies.chmodSync || fs.chmodSync;
  const resolvePath = dependencies.resolvePath || path.resolve;
  const manifest = buildPullRequestArtifactManifest(fixThreads, options);
  const outputDirectory = resolvePath(manifest.artifactsDir);

  mkdirSync(outputDirectory, { recursive: true });

  manifest.groups.forEach((group, groupIndex) => {
    writeFileSync(resolvePath(group.bodyFilePath), `${group.body}\n`, "utf8");
    const scriptPayload = buildPullRequestCreationScript(
      {
        followUpPr: group.followUpPr,
        threadCount: group.threads.length,
        threads: group.threads,
      },
      groupIndex,
      {
        baseBranch: group.baseBranch,
        bodyFilePath: group.bodyFilePath,
        commandScriptPath: group.commandScriptPath,
        headBranch: group.headBranch,
      }
    );
    writeFileSync(resolvePath(group.commandScriptPath), scriptPayload.script, "utf8");
    chmodSync(resolvePath(group.commandScriptPath), 0o755);
  });

  writeFileSync(resolvePath(manifest.manifestPath), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  return manifest;
}

function formatFixThreadsAsPullRequestPayloads(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0 } = options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  const lines = ["# Follow-up PR Payloads", ""];

  if (fixThreads.length === 0) {
    if (excludedOutdatedCount > 0) {
      lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
    }
    lines.push("No actionable fix-classified threads found.");
    return `${lines.join("\n")}\n`;
  }

  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
  }

  followUpPrGroups.forEach((group, groupIndex) => {
    const payload = buildPullRequestPayload(group, groupIndex);
    lines.push(`## Follow-up PR Group ${groupIndex + 1}: ${group.followUpPr || "<missing follow-up PR>"}`);
    lines.push("");
    lines.push(`Title: ${payload.title}`);
    lines.push("");
    lines.push("Body:");
    lines.push("```markdown");
    lines.push(payload.body);
    lines.push("```");
    lines.push("");
  });

  if (lines[lines.length - 1] === "") {
    lines.pop();
  }

  return `${lines.join("\n")}\n`;
}

function formatFixThreadsAsGhCliCommands(fixThreads, options = {}) {
  const { excludedOutdatedCount = 0, baseBranch = "main", artifactsDir = DEFAULT_ARTIFACTS_DIR } =
    options;
  const followUpPrGroups = groupFixThreadsByFollowUpPr(fixThreads);
  const lines = ["# Follow-up PR Create Commands", ""];

  if (fixThreads.length === 0) {
    if (excludedOutdatedCount > 0) {
      lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
    }
    lines.push("No actionable fix-classified threads found.");
    return `${lines.join("\n")}\n`;
  }

  if (excludedOutdatedCount > 0) {
    lines.push(`Excluded outdated fix threads: ${excludedOutdatedCount}`, "");
  }

  lines.push(`Artifacts Directory: \`${artifactsDir}\``);
  lines.push(`Artifact Manifest: \`${path.join(artifactsDir, "manifest.json")}\``);
  lines.push("");

  followUpPrGroups.forEach((group, groupIndex) => {
    const payload = buildPullRequestCreationCommand(group, groupIndex, {
      baseBranch,
      bodyFilePath: path.join(artifactsDir, `pr-178-fix-group-${groupIndex + 1}-body.md`),
    });
    lines.push(`## Follow-up PR Group ${groupIndex + 1}: ${group.followUpPr || "<missing follow-up PR>"}`);
    lines.push("");
    lines.push(`Suggested Branch: \`${payload.headBranch}\``);
    lines.push(`Suggested Body File: \`${payload.bodyFilePath}\``);
    lines.push(`Suggested Command Script: \`${payload.commandScriptPath}\``);
    lines.push(`Base Branch: \`${payload.baseBranch}\``);
    lines.push("");
    lines.push("Command:");
    lines.push("```bash");
    lines.push(payload.command);
    lines.push("```");
    lines.push("");
    lines.push("Body:");
    lines.push("```markdown");
    lines.push(payload.body);
    lines.push("```");
    lines.push("");
  });

  if (lines[lines.length - 1] === "") {
    lines.pop();
  }

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

  if (outputFormat === "pr-payload") {
    return formatFixThreadsAsPullRequestPayloads(fixThreads, options);
  }

  if (outputFormat === "gh-cli") {
    return formatFixThreadsAsGhCliCommands(fixThreads, options);
  }

  return formatFixThreadsReport(fixThreads, options);
}

function buildFixThreadsReport(options = {}, dependencies = {}) {
  const {
    docPath = DEFAULT_DOC_PATH,
    excludeOutdated = false,
    followUpPr = null,
    requireComplete = false,
    outputFormat = "text",
    baseBranch = "main",
    writeArtifactsDir = null,
  } = options;
  const threads = loadThreadInventory(docPath, dependencies);
  const activeThreads = loadThreadInventory(docPath, dependencies, {
    inventorySection: "unresolved",
  });
  const issues = collectThreadInventoryIssues(threads);

  if (requireComplete && issues.length > 0) {
    throw new Error(formatThreadInventoryIssues(issues).trimEnd());
  }

  const allFixThreads = listFixClassifiedThreads(activeThreads);
  const actionableFixThreads = listActionableFixThreads(activeThreads, { excludeOutdated });
  const excludedOutdatedCount = allFixThreads.length - actionableFixThreads.length;
  const normalizedFollowUpPr = normalizeFollowUpPrFieldValue(followUpPr);
  const fixThreads = followUpPr
    ? actionableFixThreads.filter((thread) => thread.followUpPr === normalizedFollowUpPr)
    : actionableFixThreads;

  const artifactsDir = writeArtifactsDir || DEFAULT_ARTIFACTS_DIR;
  if (writeArtifactsDir) {
    writePullRequestArtifacts(fixThreads, { baseBranch, artifactsDir }, dependencies);
  }

  return formatFixThreadsOutput(fixThreads, outputFormat, {
    excludedOutdatedCount,
    baseBranch,
    artifactsDir,
  });
}

function getCliConfiguration(argv = process.argv.slice(2)) {
  const options = {
    docPath: DEFAULT_DOC_PATH,
    excludeOutdated: false,
    followUpPr: null,
    outputFormat: "text",
    requireComplete: false,
    baseBranch: "main",
    writeArtifactsDir: null,
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

    if (argument === "--follow-up-pr") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --follow-up-pr flag requires a value.");
      }

      options.followUpPr = normalizeFollowUpPrFieldValue(value);
      if (!options.followUpPr) {
        throw new Error(`The --follow-up-pr flag requires a non-placeholder URL; received "${value}".`);
      }

      index += 1;
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

    if (argument === "--base-branch") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --base-branch flag requires a value.");
      }

      options.baseBranch = value;
      index += 1;
      continue;
    }

    if (argument === "--write-artifacts-dir") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --write-artifacts-dir flag requires a value.");
      }

      options.writeArtifactsDir = value;
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

  if (!["text", "json", "markdown", "plan", "pr-payload", "gh-cli"].includes(options.outputFormat)) {
    throw new Error(
      `Output format must be one of "text", "json", "markdown", "plan", "pr-payload", or "gh-cli"; received "${options.outputFormat}".`
    );
  }

  return options;
}

function main(argv = process.argv.slice(2)) {
  const {
    docPath,
    excludeOutdated,
    followUpPr,
    outputFormat,
    requireComplete,
    baseBranch,
    writeArtifactsDir,
  } =
    getCliConfiguration(argv);
  process.stdout.write(
    buildFixThreadsReport({
      docPath,
      excludeOutdated,
      followUpPr,
      outputFormat,
      requireComplete,
      baseBranch,
      writeArtifactsDir,
    })
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
  DEFAULT_ARTIFACTS_DIR,
  buildPullRequestCreationCommand,
  buildPullRequestCreationScript,
  buildPullRequestArtifactManifest,
  collectThreadInventoryIssues,
  formatFixThreadsAsGhCliCommands,
  formatFixThreadsAsJson,
  formatFixThreadsAsPlan,
  formatFixThreadsAsMarkdown,
  formatFixThreadsAsPullRequestPayloads,
  formatFixThreadsOutput,
  formatFixThreadsReport,
  formatThreadInventoryIssues,
  getCliConfiguration,
  buildSuggestedBranchName,
  buildPullRequestPayload,
  extractPullRequestNumber,
  groupFixThreadsByFollowUpPr,
  isEmptyInventoryThread,
  listActionableFixThreads,
  listFixClassifiedThreads,
  loadThreadInventory,
  normalizeFieldValue,
  normalizeFollowUpPrFieldValue,
  normalizeOutdatedFieldValue,
  normalizeUrlFieldValue,
  isValidFollowUpPrLink,
  parseThreadInventory,
  shellQuote,
  isPlaceholderValue,
  writePullRequestArtifacts,
};
