#!/usr/bin/env node

"use strict";

const path = require("node:path");

const {
  collectThreadInventoryIssues,
  DEFAULT_DOC_PATH,
  loadThreadInventory,
} = require("./list_fix_threads_from_doc.js");
const {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  extractUnresolvedThreads,
  getConfiguration,
  loadReviewThreadsFromFile,
  validateExpectedCount,
} = require("./list_unresolved_pr_threads.js");

function getVerifierConfiguration(argv = process.argv.slice(2), env = process.env) {
  const reviewThreadConfiguration = getConfiguration(argv, env);
  const options = {
    docPath: DEFAULT_DOC_PATH,
    expectDocCount: null,
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
    }
  }

  const expectDocCountRaw = options.expectDocCount ?? env.EXPECT_DOC_THREAD_COUNT ?? null;
  const expectDocCount =
    expectDocCountRaw === null ? null : Number.parseInt(String(expectDocCountRaw), 10);

  if (expectDocCountRaw !== null && (!Number.isInteger(expectDocCount) || expectDocCount < 0)) {
    throw new Error(
      `Expected documented thread count must be a non-negative integer; received "${expectDocCountRaw}".`
    );
  }

  return {
    ...reviewThreadConfiguration,
    docPath: options.docPath,
    expectDocCount,
  };
}

function collectInventoryVerificationIssues(documentedThreads, unresolvedThreads, options = {}) {
  const { expectDocCount = null } = options;
  const issues = collectThreadInventoryIssues(documentedThreads);

  if (expectDocCount !== null && documentedThreads.length !== expectDocCount) {
    issues.push(
      `Expected ${expectDocCount} documented thread(s), found ${documentedThreads.length}.`
    );
  }

  const documentedIds = new Set(documentedThreads.map((thread) => thread.threadId).filter(Boolean));
  const unresolvedIds = new Set(unresolvedThreads.map((thread) => thread.id).filter(Boolean));

  unresolvedThreads.forEach((thread) => {
    if (!documentedIds.has(thread.id)) {
      issues.push(`Unresolved thread ${thread.id} is missing from the inventory document.`);
    }
  });

  documentedThreads.forEach((thread) => {
    if (thread.threadId && unresolvedThreads.length > 0 && !unresolvedIds.has(thread.threadId)) {
      issues.push(`Documented thread ${thread.threadId} is not unresolved in the provided snapshot.`);
    }
  });

  return issues;
}

function formatInventoryVerificationReport(configuration, documentedThreads, unresolvedThreads, issues) {
  const repository = `${configuration.owner}/${configuration.repo}`;
  const lines = [
    `Repository: ${repository}`,
    `Pull request: #${configuration.prNumber}`,
    `Inventory document: ${configuration.docPath}`,
    `Documented threads: ${documentedThreads.length}`,
    `Unresolved threads in snapshot: ${unresolvedThreads.length}`,
  ];

  if (configuration.expectDocCount !== null) {
    lines.push(`Expected documented threads: ${configuration.expectDocCount}`);
  }

  if (configuration.expectedCount !== null) {
    lines.push(`Expected unresolved threads: ${configuration.expectedCount}`);
  }

  if (issues.length === 0) {
    lines.push("Verification: OK");
    return `${lines.join("\n")}\n`;
  }

  lines.push(`Verification: FAILED (${issues.length} issue${issues.length === 1 ? "" : "s"})`);
  issues.forEach((issue, index) => {
    lines.push(`${index + 1}. ${issue}`);
  });
  return `${lines.join("\n")}\n`;
}

function buildInventoryVerificationReport(configuration, dependencies = {}) {
  const loadInventory = dependencies.loadThreadInventory || loadThreadInventory;
  const loadThreads = dependencies.loadReviewThreadsFromFile || loadReviewThreadsFromFile;
  const documentedThreads = loadInventory(configuration.docPath);
  const unresolvedThreads = extractUnresolvedThreads(loadThreads(configuration.inputPath));
  const issues = collectInventoryVerificationIssues(documentedThreads, unresolvedThreads, {
    expectDocCount: configuration.expectDocCount,
  });
  let expectedCountError = null;

  try {
    validateExpectedCount(unresolvedThreads, configuration.expectedCount);
  } catch (error) {
    expectedCountError = error.message;
  }

  if (expectedCountError) {
    issues.push(expectedCountError);
  }

  return formatInventoryVerificationReport(
    configuration,
    documentedThreads,
    unresolvedThreads,
    issues
  );
}

function main(argv = process.argv.slice(2), env = process.env) {
  const configuration = getVerifierConfiguration(argv, env);
  const report = buildInventoryVerificationReport(configuration);
  process.stdout.write(report);

  if (report.includes("Verification: FAILED")) {
    process.exitCode = 1;
  }
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
  buildInventoryVerificationReport,
  collectInventoryVerificationIssues,
  formatInventoryVerificationReport,
  getVerifierConfiguration,
  main,
  DEFAULT_DOC_PATH,
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
};
