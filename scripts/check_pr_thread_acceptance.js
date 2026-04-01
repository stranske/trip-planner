#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const {
  DEFAULT_DOC_PATH,
  collectThreadInventoryIssues,
  isValidFollowUpPrLink,
  listFixClassifiedThreads,
  loadThreadInventory,
} = require("./list_fix_threads_from_doc.js");
const {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  extractUnresolvedThreads,
  fetchAllReviewThreads,
  loadReviewThreadsFromFile,
  parseCommandLineArguments,
  validateExpectedCount,
  writeInventoryDocument,
} = require("./list_unresolved_pr_threads.js");
const {
  collectInventoryVerificationIssues,
} = require("./verify_pr_thread_inventory.js");

function getAcceptanceConfiguration(argv = process.argv.slice(2), env = process.env) {
  const passthroughArguments = [];
  const options = {
    docPath: DEFAULT_DOC_PATH,
    expectDocCount: 4,
    expectUnresolvedCount: 0,
    githubUiConfirmed: false,
    live: false,
    outputFormat: "text",
    resultsPath: null,
    writeInventoryDoc: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--doc") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --doc flag requires a file path.");
      }

      options.docPath = path.resolve(value);
      index += 1;
      continue;
    }

    if (argument === "--expect-doc-count") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --expect-doc-count flag requires an integer value.");
      }

      options.expectDocCount = value;
      index += 1;
      continue;
    }

    if (argument === "--expect-count") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --expect-count flag requires an integer value.");
      }

      options.expectUnresolvedCount = value;
      passthroughArguments.push(argument, value);
      index += 1;
      continue;
    }

    if (argument === "--live") {
      options.live = true;
      continue;
    }

    if (argument === "--results") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --results flag requires a file path.");
      }

      options.resultsPath = path.resolve(value);
      index += 1;
      continue;
    }

    if (argument === "--github-ui-confirmed") {
      options.githubUiConfirmed = true;
      continue;
    }

    if (argument === "--write-inventory-doc") {
      options.writeInventoryDoc = true;
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

    passthroughArguments.push(argument);
  }

  if (!["text", "json"].includes(options.outputFormat)) {
    throw new Error(
      `Output format must be one of "text" or "json"; received "${options.outputFormat}".`
    );
  }

  const resultsReport = options.resultsPath ? loadResolutionResultsReport(options.resultsPath) : null;
  const parsedArguments = parseCommandLineArguments(passthroughArguments);
  const repository =
    parsedArguments.positional[0] ||
    resultsReport?.repository ||
    env.GITHUB_REPOSITORY ||
    DEFAULT_REPOSITORY;
  const prNumberRaw =
    parsedArguments.positional[1] ||
    resultsReport?.prNumber ||
    env.PR_NUMBER ||
    String(DEFAULT_PR_NUMBER);
  const prNumber = Number.parseInt(prNumberRaw, 10);
  const inputPath =
    parsedArguments.inputPath || resultsReport?.inputPath || env.REVIEW_THREADS_FILE || null;
  const token = options.live ? env.GITHUB_TOKEN : null;
  const expectDocCount = Number.parseInt(
    String(resultsReport?.expectDocCount ?? options.expectDocCount),
    10
  );
  const expectUnresolvedCount = Number.parseInt(
    String(resultsReport?.expectedCount ?? options.expectUnresolvedCount),
    10
  );
  const githubUiConfirmed = options.githubUiConfirmed || Boolean(resultsReport?.githubUiConfirmed);
  const docPath = resultsReport?.docPath || options.docPath;

  if (!repository.includes("/")) {
    throw new Error(
      `Repository must be in OWNER/REPO format; received "${repository}".`
    );
  }

  if (!Number.isInteger(prNumber) || prNumber <= 0) {
    throw new Error(`Pull request number must be a positive integer; received "${prNumberRaw}".`);
  }

  if (!Number.isInteger(expectDocCount) || expectDocCount < 0) {
    throw new Error(
      `Expected documented thread count must be a non-negative integer; received "${options.expectDocCount}".`
    );
  }

  if (!Number.isInteger(expectUnresolvedCount) || expectUnresolvedCount < 0) {
    throw new Error(
      `Expected unresolved thread count must be a non-negative integer; received "${options.expectUnresolvedCount}".`
    );
  }

  if (options.live && inputPath) {
    throw new Error("The --live and --input options are mutually exclusive.");
  }

  if (options.live && !token) {
    throw new Error("GITHUB_TOKEN is required when --live is specified.");
  }

  const [owner, repo] = repository.split("/", 2);
  return {
    owner,
    repo,
    prNumber,
    token,
    inputPath,
    docPath,
    expectDocCount,
    expectedCount: expectUnresolvedCount,
    outputFormat: options.outputFormat,
    githubUiConfirmed,
    live: options.live,
    resultsPath: options.resultsPath,
    writeInventoryDoc: options.writeInventoryDoc,
  };
}

function loadResolutionResultsReport(resultsPath, dependencies = {}) {
  const readFileSync = dependencies.readFileSync || fs.readFileSync;
  let parsedReport;

  try {
    parsedReport = JSON.parse(readFileSync(resultsPath, "utf8"));
  } catch (error) {
    throw new Error(
      `Could not parse results report "${resultsPath}": ${error.message}`
    );
  }

  if (!parsedReport || typeof parsedReport !== "object") {
    throw new Error(`Results report "${resultsPath}" must contain a JSON object.`);
  }

  const acceptance = parsedReport.acceptance;
  if (!acceptance || typeof acceptance !== "object") {
    throw new Error(
      `Results report "${resultsPath}" must contain an "acceptance" object.`
    );
  }

  const docPath = parsedReport.inventoryUpdate?.docPath || acceptance.docPath || DEFAULT_DOC_PATH;
  const repository = acceptance.repository || null;
  const prNumber = acceptance.prNumber ? String(acceptance.prNumber) : null;
  const expectDocCount = acceptance.expectDocCount;
  const expectedCount = acceptance.expectedCount;
  const inputPath =
    parsedReport.remainingSnapshotPath ||
    (acceptance.inputPath && !String(acceptance.inputPath).startsWith("<")
      ? acceptance.inputPath
      : null);
  const githubUiCriterion = Array.isArray(acceptance.criteria)
    ? acceptance.criteria.find((criterion) => criterion.id === "github_ui")
    : null;

  return {
    repository,
    prNumber,
    docPath,
    expectDocCount,
    expectedCount,
    inputPath,
    githubUiConfirmed: githubUiCriterion?.status === "pass",
  };
}

function formatCriterionLine(status, label, details) {
  return `- [${status}] ${label}: ${details}`;
}

async function evaluateAcceptance(configuration, dependencies = {}) {
  const loadInventory = dependencies.loadThreadInventory || loadThreadInventory;
  const loadThreads = dependencies.loadReviewThreadsFromFile || loadReviewThreadsFromFile;
  const fetchThreads = dependencies.fetchAllReviewThreads || fetchAllReviewThreads;
  const syncInventoryDocument = dependencies.writeInventoryDocument || writeInventoryDocument;

  const repository = `${configuration.owner}/${configuration.repo}`;
  const verificationMode = configuration.inputPath
    ? "snapshot"
    : configuration.token
      ? "live"
      : "none";
  let documentedThreads = loadInventory(configuration.docPath);
  let activeDocumentedThreads = loadInventory(configuration.docPath, {}, {
    inventorySection: "unresolved",
  });
  let docIssues = collectThreadInventoryIssues(documentedThreads);
  let fixThreads = listFixClassifiedThreads(documentedThreads);
  let fixThreadsMissingOrInvalidFollowUpPr = fixThreads.filter(
    (thread) => !isValidFollowUpPrLink(thread.followUpPr)
  );

  const criteria = [
    {
      id: "doc_inventory",
      label: `docs/pr-178-unresolved-threads.md records ${configuration.expectDocCount} complete thread entries`,
      status:
        documentedThreads.length === configuration.expectDocCount && docIssues.length === 0
          ? "pass"
          : "fail",
      details:
        docIssues.length === 0 && documentedThreads.length === configuration.expectDocCount
          ? `Found ${documentedThreads.length} documented thread entries with complete metadata.`
          : `Found ${documentedThreads.length} documented thread entries; ${docIssues.length} completeness issue(s) remain.`,
      issues: docIssues,
    },
    {
      id: "fix_follow_up_prs",
      label: "fix-classified threads have follow-up PR links",
      status: fixThreadsMissingOrInvalidFollowUpPr.length === 0 ? "pass" : "fail",
      details:
        fixThreads.length === 0
          ? "No fix-classified threads are currently documented."
          : fixThreadsMissingOrInvalidFollowUpPr.length === 0
            ? `All ${fixThreads.length} fix-classified thread(s) include follow-up PR links.`
            : `${fixThreadsMissingOrInvalidFollowUpPr.length} of ${fixThreads.length} fix-classified thread(s) are missing valid follow-up PR links.`,
      issues: fixThreadsMissingOrInvalidFollowUpPr.map(
        (thread) =>
          `${thread.threadId || "<missing thread id>"}: ${
            thread.followUpPr
              ? `invalid follow-up PR "${thread.followUpPr}"`
              : "missing follow-up PR"
          }`
      ),
    },
  ];

  let unresolvedThreads = null;
  let inventoryDocumentUpdated = false;

  if (configuration.inputPath || configuration.token) {
    const rawThreads = configuration.inputPath
      ? loadThreads(configuration.inputPath)
      : await fetchThreads(configuration);
    unresolvedThreads = extractUnresolvedThreads(rawThreads);

    if (configuration.writeInventoryDoc) {
      syncInventoryDocument(configuration.docPath, unresolvedThreads);
      inventoryDocumentUpdated = true;
      documentedThreads = loadInventory(configuration.docPath);
      activeDocumentedThreads = loadInventory(configuration.docPath, {}, {
        inventorySection: "unresolved",
      });
      docIssues = collectThreadInventoryIssues(documentedThreads);
      fixThreads = listFixClassifiedThreads(documentedThreads);
      fixThreadsMissingOrInvalidFollowUpPr = fixThreads.filter(
        (thread) => !isValidFollowUpPrLink(thread.followUpPr)
      );
      criteria[0] = {
        ...criteria[0],
        status:
          documentedThreads.length === configuration.expectDocCount && docIssues.length === 0
            ? "pass"
            : "fail",
        details:
          docIssues.length === 0 && documentedThreads.length === configuration.expectDocCount
            ? `Found ${documentedThreads.length} documented thread entries with complete metadata.`
            : `Found ${documentedThreads.length} documented thread entries; ${docIssues.length} completeness issue(s) remain.`,
        issues: docIssues,
      };
      criteria[1] = {
        ...criteria[1],
        status: fixThreadsMissingOrInvalidFollowUpPr.length === 0 ? "pass" : "fail",
        details:
          fixThreads.length === 0
            ? "No fix-classified threads are currently documented."
            : fixThreadsMissingOrInvalidFollowUpPr.length === 0
              ? `All ${fixThreads.length} fix-classified thread(s) include follow-up PR links.`
              : `${fixThreadsMissingOrInvalidFollowUpPr.length} of ${fixThreads.length} fix-classified thread(s) are missing valid follow-up PR links.`,
        issues: fixThreadsMissingOrInvalidFollowUpPr.map(
          (thread) =>
            `${thread.threadId || "<missing thread id>"}: ${
              thread.followUpPr
                ? `invalid follow-up PR "${thread.followUpPr}"`
                : "missing follow-up PR"
            }`
        ),
      };
    }

    const inventoryIssues = collectInventoryVerificationIssues(
      documentedThreads,
      unresolvedThreads,
      {
        expectDocCount: configuration.expectDocCount,
        activeDocumentedThreads,
      }
    );

    try {
      validateExpectedCount(unresolvedThreads, configuration.expectedCount);
    } catch (error) {
      inventoryIssues.push(error.message);
    }

    criteria.push({
      id: "snapshot_verification",
      label: `review-thread snapshot verifies ${configuration.expectedCount} unresolved thread(s)`,
      status: inventoryIssues.length === 0 ? "pass" : "fail",
      details:
        inventoryIssues.length === 0
          ? `Snapshot verification passed with ${unresolvedThreads.length} unresolved thread(s).`
          : `Snapshot verification found ${inventoryIssues.length} issue(s) with ${unresolvedThreads.length} unresolved thread(s).`,
      issues: inventoryIssues,
    });
  } else {
    criteria.push({
      id: "snapshot_verification",
      label: `review-thread snapshot verifies ${configuration.expectedCount} unresolved thread(s)`,
      status: "blocked",
      details:
        "Provide --input <snapshot.json> or GITHUB_TOKEN to verify unresolved-thread state.",
      issues: [],
    });
  }

  criteria.push({
    id: "github_ui",
    label: "GitHub UI shows no unresolved inline review threads",
    status: configuration.githubUiConfirmed ? "pass" : "manual",
    details: configuration.githubUiConfirmed
      ? "Manual GitHub UI verification was explicitly confirmed for this run."
      : "Repo-local tooling cannot verify the live GitHub UI state without explicit confirmation.",
    issues: [],
  });

  const overallStatus = criteria.every((criterion) => criterion.status === "pass")
    ? "pass"
    : criteria.some((criterion) => criterion.status === "fail")
      ? "fail"
      : criteria.some((criterion) => criterion.status === "blocked")
        ? "blocked"
        : criteria.some((criterion) => criterion.status === "manual")
          ? "manual"
          : "blocked";

  return {
    repository,
    prNumber: configuration.prNumber,
    docPath: configuration.docPath,
    verificationMode,
    inputPath: configuration.inputPath,
    expectDocCount: configuration.expectDocCount,
    expectedCount: configuration.expectedCount,
    documentedThreadCount: documentedThreads.length,
    unresolvedThreadCount: unresolvedThreads ? unresolvedThreads.length : null,
    inventoryDocumentUpdated,
    criteria,
    overallStatus,
  };
}

function formatAcceptanceReport(result, outputFormat = "text") {
  if (outputFormat === "json") {
    return `${JSON.stringify(result, null, 2)}\n`;
  }

  const lines = [
    `Repository: ${result.repository}`,
    `Pull request: #${result.prNumber}`,
    `Inventory document: ${result.docPath}`,
    `Review-thread verification: ${formatVerificationMode(result)}`,
    `Overall status: ${result.overallStatus.toUpperCase()}`,
    "",
    "Acceptance criteria:",
  ];

  if (result.inventoryDocumentUpdated) {
    lines.splice(4, 0, "Inventory document sync: UPDATED");
  }

  result.criteria.forEach((criterion) => {
    lines.push(formatCriterionLine(criterion.status.toUpperCase(), criterion.label, criterion.details));
    criterion.issues.forEach((issue) => {
      lines.push(`  - ${issue}`);
    });
  });

  return `${lines.join("\n")}\n`;
}

function formatVerificationMode(result) {
  if (result.verificationMode === "snapshot") {
    return `SNAPSHOT (${result.inputPath})`;
  }

  if (result.verificationMode === "live") {
    return "LIVE API";
  }

  return "NOT RUN";
}

async function main(argv = process.argv.slice(2), env = process.env) {
  const configuration = getAcceptanceConfiguration(argv, env);
  const result = await evaluateAcceptance(configuration);
  process.stdout.write(formatAcceptanceReport(result, configuration.outputFormat));

  if (result.overallStatus !== "pass") {
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}

module.exports = {
  evaluateAcceptance,
  formatVerificationMode,
  formatAcceptanceReport,
  getAcceptanceConfiguration,
  loadResolutionResultsReport,
  main,
  DEFAULT_DOC_PATH,
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
};
