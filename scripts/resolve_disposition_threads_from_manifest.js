#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const childProcess = require("node:child_process");

const DEFAULT_MANIFEST_PATH = path.resolve(".tmp/pr-thread-disposition/manifest.json");

function parseCliArguments(argv = process.argv.slice(2)) {
  const options = {
    manifestPath: DEFAULT_MANIFEST_PATH,
    execute: false,
    outputFormat: "text",
    resultsPath: null,
    threadId: null,
    threadIndex: null,
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

    if (argument === "--write-results") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --write-results flag requires a file path.");
      }

      options.resultsPath = value;
      index += 1;
      continue;
    }

    if (argument === "--thread-id") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --thread-id flag requires a value.");
      }

      options.threadId = value;
      index += 1;
      continue;
    }

    if (argument === "--thread-index") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --thread-index flag requires a 1-based integer value.");
      }

      const parsedValue = Number.parseInt(value, 10);
      if (!Number.isInteger(parsedValue) || parsedValue <= 0) {
        throw new Error(`Thread index must be a positive integer; received "${value}".`);
      }

      options.threadIndex = parsedValue;
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

  if (!manifest || typeof manifest !== "object" || !Array.isArray(manifest.threads)) {
    throw new Error(`Manifest "${manifestPath}" must contain a "threads" array.`);
  }

  return manifest;
}

function validateManifestThread(thread, threadIndex) {
  const issues = [];
  const displayThreadNumber = threadIndex + 1;

  if (!thread || typeof thread !== "object") {
    return [`Thread ${displayThreadNumber} is not an object.`];
  }

  if (!thread.threadId) {
    issues.push(`Thread ${displayThreadNumber} is missing threadId.`);
  }

  if (!thread.replyQuery) {
    issues.push(`Thread ${displayThreadNumber} is missing replyQuery.`);
  }

  if (!thread.replyVariables || typeof thread.replyVariables !== "object") {
    issues.push(`Thread ${displayThreadNumber} is missing replyVariables.`);
  }

  if (!thread.resolveQuery) {
    issues.push(`Thread ${displayThreadNumber} is missing resolveQuery.`);
  }

  if (!thread.resolveVariables || typeof thread.resolveVariables !== "object") {
    issues.push(`Thread ${displayThreadNumber} is missing resolveVariables.`);
  }

  return issues;
}

function selectManifestThreads(manifest, options = {}) {
  const threadIndex = options.threadIndex ?? null;
  const threadId = options.threadId ?? null;
  const selectedThreads = manifest.threads
    .map((thread, index) => ({
      ...thread,
      manifestThreadNumber: index + 1,
    }))
    .filter((thread) => {
      if (threadIndex !== null && thread.manifestThreadNumber !== threadIndex) {
        return false;
      }

      if (threadId && thread.threadId !== threadId) {
        return false;
      }

      return true;
    });

  if (selectedThreads.length === 0) {
    const selector = threadId ? `thread ID "${threadId}"` : `thread index ${threadIndex}`;
    throw new Error(`No manifest threads matched ${selector}.`);
  }

  return selectedThreads;
}

function buildGhGraphqlArgs(query, variables = {}) {
  const args = ["api", "graphql", "-f", `query=${query}`];

  Object.entries(variables).forEach(([key, value]) => {
    args.push("-F", `${key}=${String(value)}`);
  });

  return args;
}

function runGhGraphql(args, dependencies = {}) {
  if (dependencies.spawnSync) {
    const result = dependencies.spawnSync("gh", args, { encoding: "utf8" });

    if (result?.error) {
      throw result.error;
    }

    if (result?.signal) {
      throw new Error(`gh api graphql terminated by signal ${result.signal}.`);
    }

    return {
      status: Number.isInteger(result?.status) ? result.status : 0,
      stdout: String(result?.stdout || "").trim(),
      stderr: String(result?.stderr || "").trim(),
    };
  }

  const execFileSync = dependencies.execFileSync || childProcess.execFileSync;
  return {
    status: 0,
    stdout: String(execFileSync("gh", args, { encoding: "utf8" })).trim(),
    stderr: "",
  };
}

function combineCommandOutput(stdout, stderr) {
  return [stdout, stderr].filter(Boolean).join("\n").trim();
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
  const mkdirSync = dependencies.mkdirSync || fs.mkdirSync;
  const writeFileSync = dependencies.writeFileSync || fs.writeFileSync;
  mkdirSync(path.dirname(resultsPath), { recursive: true });
  writeFileSync(resultsPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

function executeManifestThreads(options = {}, dependencies = {}) {
  const manifest = loadManifest(options.manifestPath, dependencies);
  const threads = selectManifestThreads(manifest, options);
  const validationIssues = threads.flatMap((thread, index) =>
    validateManifestThread(thread, index)
  );

  if (validationIssues.length > 0) {
    throw new Error(validationIssues.join("\n"));
  }

  const results = threads.map((thread, index) => {
    const replyArgs = buildGhGraphqlArgs(thread.replyQuery, thread.replyVariables);
    const resolveArgs = buildGhGraphqlArgs(thread.resolveQuery, thread.resolveVariables);
    const result = {
      threadNumber: index + 1,
      manifestThreadNumber: thread.manifestThreadNumber,
      threadId: thread.threadId,
      originalThreadUrl: thread.originalThreadUrl || null,
      location: thread.location || null,
      scriptPath: thread.scriptPath
        ? resolveManifestRelativePath(options.manifestPath, thread.scriptPath)
        : null,
      mode: options.execute ? "execute" : "dry-run",
      replyCommand: ["gh", ...replyArgs].join(" "),
      resolveCommand: ["gh", ...resolveArgs].join(" "),
      replyOutput: null,
      resolveOutput: null,
      replyExitStatus: null,
      resolveExitStatus: null,
    };

    if (options.execute) {
      const replyResult = runGhGraphql(replyArgs, dependencies);
      result.replyExitStatus = replyResult.status;
      result.replyOutput = combineCommandOutput(replyResult.stdout, replyResult.stderr);

      if (replyResult.status !== 0) {
        throw new Error(
          `Thread ${thread.manifestThreadNumber} reply command failed with exit code ${replyResult.status}: ${result.replyOutput || "<no output>"}`
        );
      }

      const resolveResult = runGhGraphql(resolveArgs, dependencies);
      result.resolveExitStatus = resolveResult.status;
      result.resolveOutput = combineCommandOutput(resolveResult.stdout, resolveResult.stderr);

      if (resolveResult.status !== 0) {
        throw new Error(
          `Thread ${thread.manifestThreadNumber} resolve command failed with exit code ${resolveResult.status}: ${result.resolveOutput || "<no output>"}`
        );
      }
    }

    return result;
  });

  const report = {
    manifestPath: options.manifestPath,
    execute: options.execute,
    threadCount: results.length,
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
    report.execute ? "# Disposition Thread Resolution" : "# Disposition Thread Dry Run",
    "",
    `Manifest: \`${report.manifestPath}\``,
    `Selected Threads: ${report.threadCount}`,
  ];

  if (report.resultsPath) {
    lines.push(`Results File: \`${report.resultsPath}\``);
  }

  report.results.forEach((result) => {
    lines.push("");
    lines.push(
      `## Thread ${result.threadNumber} (Manifest Thread ${result.manifestThreadNumber}): ${result.threadId}`
    );
    lines.push("");
    lines.push(`- Mode: ${result.mode}`);
    lines.push(`- Original Thread URL: ${result.originalThreadUrl || "<missing original thread URL>"}`);
    lines.push(`- Location: ${result.location || "<missing location>"}`);
    if (result.scriptPath) {
      lines.push(`- Script Path: \`${result.scriptPath}\``);
    }
    lines.push(`- Reply Command: \`${result.replyCommand}\``);
    lines.push(`- Resolve Command: \`${result.resolveCommand}\``);
    if (result.replyExitStatus !== null) {
      lines.push(`- Reply Exit Status: ${result.replyExitStatus}`);
    }
    if (result.resolveExitStatus !== null) {
      lines.push(`- Resolve Exit Status: ${result.resolveExitStatus}`);
    }
    if (result.replyOutput) {
      lines.push(`- Reply Output: ${result.replyOutput}`);
    }
    if (result.resolveOutput) {
      lines.push(`- Resolve Output: ${result.resolveOutput}`);
    }
  });

  return `${lines.join("\n")}\n`;
}

function main(argv = process.argv.slice(2)) {
  const options = parseCliArguments(argv);
  const report = executeManifestThreads(options);
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
  buildGhGraphqlArgs,
  combineCommandOutput,
  DEFAULT_MANIFEST_PATH,
  executeManifestThreads,
  formatExecutionReport,
  loadManifest,
  parseCliArguments,
  resolveManifestRelativePath,
  runGhGraphql,
  selectManifestThreads,
  validateManifestThread,
  writeExecutionResults,
};
