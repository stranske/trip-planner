#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const childProcess = require("node:child_process");

function parseCliArguments(argv = process.argv.slice(2)) {
  const options = {
    manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
    execute: false,
    outputFormat: "text",
    followUpPr: null,
    groupIndex: null,
    resultsPath: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--manifest") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --manifest flag requires a file path.");
      }

      options.manifestPath = path.resolve(value);
      index += 1;
      continue;
    }

    if (argument === "--execute") {
      options.execute = true;
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

    if (argument === "--follow-up-pr") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --follow-up-pr flag requires a value.");
      }

      options.followUpPr = value;
      index += 1;
      continue;
    }

    if (argument === "--group-index") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --group-index flag requires a 1-based integer value.");
      }

      const parsed = Number.parseInt(value, 10);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        throw new Error(`Group index must be a positive integer; received "${value}".`);
      }

      options.groupIndex = parsed;
      index += 1;
      continue;
    }

    if (argument === "--write-results") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --write-results flag requires a file path.");
      }

      options.resultsPath = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown option: ${argument}`);
  }

  if (!["text", "json"].includes(options.outputFormat)) {
    throw new Error(
      `Output format must be one of "text" or "json"; received "${options.outputFormat}".`
    );
  }

  return options;
}

function loadManifest(manifestPath, dependencies = {}) {
  const readFileSync = dependencies.readFileSync || fs.readFileSync;
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));

  if (!manifest || typeof manifest !== "object" || !Array.isArray(manifest.groups)) {
    throw new Error(`Manifest "${manifestPath}" must contain a "groups" array.`);
  }

  return manifest;
}

function validateManifestGroup(group, groupIndex) {
  const issues = [];
  const displayGroupNumber = group?.manifestGroupNumber || groupIndex + 1;

  if (!group || typeof group !== "object") {
    return [`Group ${displayGroupNumber} is not an object.`];
  }

  if (!group.followUpPr) {
    issues.push(`Group ${displayGroupNumber} is missing followUpPr.`);
  }

  if (!group.title) {
    issues.push(`Group ${displayGroupNumber} is missing title.`);
  }

  if (!group.baseBranch) {
    issues.push(`Group ${displayGroupNumber} is missing baseBranch.`);
  }

  if (!group.headBranch) {
    issues.push(`Group ${displayGroupNumber} is missing headBranch.`);
  }

  if (!group.bodyFilePath) {
    issues.push(`Group ${displayGroupNumber} is missing bodyFilePath.`);
  }

  return issues;
}

function selectManifestGroups(manifest, options = {}) {
  const selectedGroups = manifest.groups
    .map((group, index) => ({
      ...group,
      manifestGroupNumber: index + 1,
    }))
    .filter((group) => {
      if (options.groupIndex !== null && group.manifestGroupNumber !== options.groupIndex) {
        return false;
      }

      if (options.followUpPr && group.followUpPr !== options.followUpPr) {
        return false;
      }

      return true;
    });

  if (selectedGroups.length === 0) {
    const selector = options.followUpPr
      ? `follow-up PR "${options.followUpPr}"`
      : `group index ${options.groupIndex}`;
    throw new Error(`No manifest groups matched ${selector}.`);
  }

  return selectedGroups;
}

function buildGhPrCreateArgs(group) {
  return [
    "pr",
    "create",
    "--base",
    group.baseBranch,
    "--head",
    group.headBranch,
    "--title",
    group.title,
    "--body-file",
    group.bodyFilePath,
  ];
}

function extractCreatedPullRequestUrl(output) {
  const normalizedOutput = String(output || "").trim();
  const match = normalizedOutput.match(
    /https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/\d+(?:[/?#][^\s]*)?/i
  );

  return match ? match[0] : null;
}

function resolveManifestRelativePath(manifestPath, targetPath) {
  if (!targetPath) {
    return targetPath;
  }

  if (path.isAbsolute(targetPath)) {
    return targetPath;
  }

  return path.resolve(path.dirname(manifestPath), targetPath);
}

function writeExecutionResults(report, resultsPath, dependencies = {}) {
  const writeFileSync = dependencies.writeFileSync || fs.writeFileSync;
  writeFileSync(resultsPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

function executeManifestGroups(options = {}, dependencies = {}) {
  const manifest = loadManifest(options.manifestPath, dependencies);
  const statSync = dependencies.statSync || fs.statSync;
  const execFileSync = dependencies.execFileSync || childProcess.execFileSync;
  const groups = selectManifestGroups(manifest, options);

  const validationIssues = groups.flatMap((group, index) =>
    validateManifestGroup(group, index)
  );
  if (validationIssues.length > 0) {
    throw new Error(validationIssues.join("\n"));
  }

  const results = groups.map((group, index) => {
    const resolvedBodyFilePath = resolveManifestRelativePath(
      options.manifestPath,
      group.bodyFilePath
    );
    let bodyFileStat;
    try {
      bodyFileStat = statSync(resolvedBodyFilePath);
    } catch (error) {
      throw new Error(
        `Group ${group.manifestGroupNumber} body file does not exist: ${resolvedBodyFilePath}`
      );
    }

    if (typeof bodyFileStat?.isFile === "function" && !bodyFileStat.isFile()) {
      throw new Error(
        `Group ${group.manifestGroupNumber} body file is not a regular file: ${resolvedBodyFilePath}`
      );
    }

    const args = buildGhPrCreateArgs({
      ...group,
      bodyFilePath: resolvedBodyFilePath,
    });
    const result = {
      groupNumber: index + 1,
      manifestGroupNumber: group.manifestGroupNumber,
      followUpPr: group.followUpPr,
      title: group.title,
      baseBranch: group.baseBranch,
      headBranch: group.headBranch,
      bodyFilePath: resolvedBodyFilePath,
      command: ["gh", ...args].join(" "),
      mode: options.execute ? "execute" : "dry-run",
      output: null,
      createdPullRequestUrl: null,
    };

    if (options.execute) {
      result.output = String(execFileSync("gh", args, { encoding: "utf8" })).trim();
      result.createdPullRequestUrl = extractCreatedPullRequestUrl(result.output);
      if (!result.createdPullRequestUrl) {
        throw new Error(
          `Group ${group.manifestGroupNumber} gh pr create output did not include a pull request URL.`
        );
      }
    }

    return result;
  });

  const report = {
    manifestPath: options.manifestPath,
    execute: options.execute,
    groupCount: results.length,
    results,
  };

  if (options.resultsPath) {
    report.resultsPath = resolveManifestRelativePath(options.manifestPath, options.resultsPath);
    writeExecutionResults(report, report.resultsPath, dependencies);
  }

  return report;
}

function formatExecutionReport(report, outputFormat = "text") {
  if (outputFormat === "json") {
    return `${JSON.stringify(report, null, 2)}\n`;
  }

  const lines = [
    report.execute ? "# Follow-up PR Creation" : "# Follow-up PR Dry Run",
    "",
    `Manifest: \`${report.manifestPath}\``,
    `Selected Groups: ${report.groupCount}`,
  ];

  if (report.resultsPath) {
    lines.push(`Results File: \`${report.resultsPath}\``);
  }

  report.results.forEach((result) => {
    lines.push("");
    lines.push(
      `## Group ${result.groupNumber} (Manifest Group ${result.manifestGroupNumber}): ${result.followUpPr}`
    );
    lines.push("");
    lines.push(`- Mode: ${result.mode}`);
    lines.push(`- Base Branch: \`${result.baseBranch}\``);
    lines.push(`- Head Branch: \`${result.headBranch}\``);
    lines.push(`- Body File: \`${result.bodyFilePath}\``);
    lines.push(`- Command: \`${result.command}\``);
    if (result.createdPullRequestUrl) {
      lines.push(`- Created PR: ${result.createdPullRequestUrl}`);
    }
    if (result.output) {
      lines.push(`- Output: ${result.output}`);
    }
  });

  return `${lines.join("\n")}\n`;
}

function main(argv = process.argv.slice(2)) {
  const options = parseCliArguments(argv);
  const report = executeManifestGroups(options);
  process.stdout.write(formatExecutionReport(report, options.outputFormat));
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
  buildGhPrCreateArgs,
  executeManifestGroups,
  extractCreatedPullRequestUrl,
  formatExecutionReport,
  loadManifest,
  main,
  parseCliArguments,
  resolveManifestRelativePath,
  selectManifestGroups,
  validateManifestGroup,
  writeExecutionResults,
};
