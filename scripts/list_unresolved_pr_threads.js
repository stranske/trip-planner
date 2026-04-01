#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const https = require("node:https");

const DEFAULT_REPOSITORY = "stranske/trip-planner";
const DEFAULT_PR_NUMBER = 178;
const GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql";

function parseCommandLineArguments(argv = process.argv.slice(2)) {
  const positional = [];
  let inputPath = null;
  let expectedCount = null;
  let outputFormat = "text";

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--input") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --input flag requires a file path.");
      }

      inputPath = value;
      index += 1;
      continue;
    }

    if (argument === "--format") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --format flag requires a value.");
      }

      outputFormat = value;
      index += 1;
      continue;
    }

    if (argument === "--expect-count") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("The --expect-count flag requires an integer value.");
      }

      expectedCount = value;
      index += 1;
      continue;
    }

    positional.push(argument);
  }

  return {
    expectedCount,
    inputPath,
    outputFormat,
    positional,
  };
}

function getConfiguration(argv = process.argv.slice(2), env = process.env) {
  const parsedArguments = parseCommandLineArguments(argv);
  const repository =
    parsedArguments.positional[0] || env.GITHUB_REPOSITORY || DEFAULT_REPOSITORY;
  const prNumberRaw =
    parsedArguments.positional[1] || env.PR_NUMBER || String(DEFAULT_PR_NUMBER);
  const token = env.GITHUB_TOKEN;
  const inputPath = parsedArguments.inputPath || env.REVIEW_THREADS_FILE || null;
  const outputFormat = parsedArguments.outputFormat || "text";
  const expectedCountRaw = parsedArguments.expectedCount ?? env.EXPECT_UNRESOLVED_COUNT ?? null;
  const prNumber = Number.parseInt(prNumberRaw, 10);
  const expectedCount =
    expectedCountRaw === null ? null : Number.parseInt(String(expectedCountRaw), 10);

  if (!repository.includes("/")) {
    throw new Error(
      `Repository must be in OWNER/REPO format; received "${repository}".`
    );
  }

  if (!Number.isInteger(prNumber) || prNumber <= 0) {
    throw new Error(`Pull request number must be a positive integer; received "${prNumberRaw}".`);
  }

  if (!token && !inputPath) {
    throw new Error("GITHUB_TOKEN is required to query GitHub review threads.");
  }

  if (!["text", "json", "markdown"].includes(outputFormat)) {
    throw new Error(
      `Output format must be one of "text", "json", or "markdown"; received "${outputFormat}".`
    );
  }

  if (expectedCountRaw !== null && (!Number.isInteger(expectedCount) || expectedCount < 0)) {
    throw new Error(
      `Expected unresolved thread count must be a non-negative integer; received "${expectedCountRaw}".`
    );
  }

  const [owner, repo] = repository.split("/", 2);
  return { owner, repo, prNumber, token, inputPath, outputFormat, expectedCount };
}

function buildReviewThreadsQuery() {
  return `
    query ReviewThreads($owner: String!, $repo: String!, $prNumber: Int!, $after: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $prNumber) {
          reviewThreads(first: 100, after: $after) {
            nodes {
              id
              isResolved
              isOutdated
              path
              line
              originalLine
              comments(first: 20) {
                nodes {
                  id
                  body
                  createdAt
                  url
                  author {
                    login
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }
    }
  `;
}

function requestGraphql({ query, variables, token, request = https.request }) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ query, variables });
    const req = request(
      GITHUB_GRAPHQL_ENDPOINT,
      {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${token}`,
          "Content-Length": Buffer.byteLength(payload),
          "Content-Type": "application/json",
          "User-Agent": "trip-planner-review-thread-audit",
          "X-GitHub-Api-Version": "2022-11-28",
        },
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`GitHub GraphQL request failed (${res.statusCode}): ${body}`));
            return;
          }

          try {
            const parsed = JSON.parse(body);
            if (parsed.errors?.length) {
              reject(
                new Error(
                  `GitHub GraphQL returned errors: ${parsed.errors
                    .map((error) => error.message)
                    .join("; ")}`
                )
              );
              return;
            }

            resolve(parsed.data);
          } catch (error) {
            reject(new Error(`Unable to parse GitHub GraphQL response: ${error.message}`));
          }
        });
      }
    );

    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

async function fetchAllReviewThreads(configuration, dependencies = {}) {
  const query = buildReviewThreadsQuery();
  const executeGraphql = dependencies.requestGraphql || requestGraphql;
  const threads = [];
  let after = null;

  while (true) {
    const data = await executeGraphql({
      query,
      variables: {
        owner: configuration.owner,
        repo: configuration.repo,
        prNumber: configuration.prNumber,
        after,
      },
      token: configuration.token,
    });

    const pullRequest = data?.repository?.pullRequest;
    if (!pullRequest) {
      throw new Error(
        `Pull request #${configuration.prNumber} was not found in ${configuration.owner}/${configuration.repo}.`
      );
    }

    const reviewThreads = pullRequest.reviewThreads;
    threads.push(...(reviewThreads?.nodes || []));

    if (!reviewThreads?.pageInfo?.hasNextPage) {
      return threads;
    }

    after = reviewThreads.pageInfo.endCursor;
  }
}

function extractThreadsFromSnapshot(snapshot) {
  if (Array.isArray(snapshot)) {
    return snapshot;
  }

  if (Array.isArray(snapshot?.threads)) {
    return snapshot.threads;
  }

  const graphqlThreads = snapshot?.data?.repository?.pullRequest?.reviewThreads?.nodes;
  if (Array.isArray(graphqlThreads)) {
    return graphqlThreads;
  }

  throw new Error("Review thread snapshot did not contain a supported thread collection.");
}

function loadReviewThreadsFromFile(inputPath, dependencies = {}) {
  const readFileSync = dependencies.readFileSync || fs.readFileSync;
  let parsedSnapshot;

  try {
    parsedSnapshot = JSON.parse(readFileSync(inputPath, "utf8"));
  } catch (error) {
    throw new Error(`Unable to load review threads from "${inputPath}": ${error.message}`);
  }

  return extractThreadsFromSnapshot(parsedSnapshot);
}

function normalizeBody(body) {
  return String(body || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractUnresolvedThreads(threads) {
  return threads
    .filter((thread) => thread && !thread.isResolved)
    .map((thread) => {
      const comments = (thread.comments?.nodes || []).map((comment) => ({
        id: comment.id,
        author: comment.author?.login || "unknown",
        body: normalizeBody(comment.body),
        createdAt: comment.createdAt,
        url: comment.url || null,
      }));

      return {
        id: thread.id,
        isOutdated: Boolean(thread.isOutdated),
        path: thread.path || "unknown",
        line: thread.line ?? thread.originalLine ?? null,
        originalThreadUrl: comments.find((comment) => comment.url)?.url || null,
        comments,
      };
    });
}

function formatUnresolvedThreadsReport(repository, prNumber, unresolvedThreads) {
  const lines = [
    `Repository: ${repository}`,
    `Pull request: #${prNumber}`,
    `Unresolved review threads: ${unresolvedThreads.length}`,
  ];

  if (unresolvedThreads.length === 0) {
    lines.push("No unresolved inline review threads found.");
    return `${lines.join("\n")}\n`;
  }

  unresolvedThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(
      `${index + 1}. ${thread.id} (${thread.path}:${thread.line ?? "unknown"}${
        thread.isOutdated ? ", outdated" : ""
      })`
    );

    if (thread.comments.length === 0) {
      lines.push("   - No thread comments returned by the API.");
      return;
    }

    thread.comments.forEach((comment) => {
      lines.push(`   - ${comment.author}: ${comment.body || "<empty>"}`);
    });
  });

  return `${lines.join("\n")}\n`;
}

function formatUnresolvedThreadsAsJson(repository, prNumber, unresolvedThreads) {
  return `${JSON.stringify(
    {
      repository,
      prNumber,
      unresolvedThreads,
    },
    null,
    2
  )}\n`;
}

function formatUnresolvedThreadsAsMarkdown(repository, prNumber, unresolvedThreads) {
  const lines = [
    `# PR #${prNumber} Unresolved Thread Inventory`,
    "",
    `Generated from \`${repository}\` PR #${prNumber} review threads.`,
    "",
    `Unresolved review threads: ${unresolvedThreads.length}`,
  ];

  if (unresolvedThreads.length === 0) {
    lines.push("", "No unresolved inline review threads found.");
    return `${lines.join("\n")}\n`;
  }

  unresolvedThreads.forEach((thread, index) => {
    lines.push("");
    lines.push(`### Thread ${index + 1}`);
    lines.push("");
    lines.push(`- Thread ID: ${thread.id}`);
    lines.push(`- Original Thread URL: ${thread.originalThreadUrl || ""}`);
    lines.push(`- Location: ${thread.path}:${thread.line ?? "unknown"}`);
    lines.push("- Classification:");
    lines.push("- Follow-up PR:");
    lines.push("- Rationale:");
    lines.push(`- Content: ${formatThreadContent(thread.comments)}`);
    lines.push(`- Outdated: ${thread.isOutdated ? "yes" : "no"}`);
  });

  return `${lines.join("\n")}\n`;
}

function formatThreadContent(comments) {
  if (comments.length === 0) {
    return "No thread comments returned by the API.";
  }

  return comments
    .map((comment) => `${comment.author}: ${comment.body || "<empty>"}`)
    .join(" | ");
}

function formatOutput(repository, prNumber, unresolvedThreads, outputFormat = "text") {
  if (outputFormat === "json") {
    return formatUnresolvedThreadsAsJson(repository, prNumber, unresolvedThreads);
  }

  if (outputFormat === "markdown") {
    return formatUnresolvedThreadsAsMarkdown(repository, prNumber, unresolvedThreads);
  }

  return formatUnresolvedThreadsReport(repository, prNumber, unresolvedThreads);
}

function validateExpectedCount(unresolvedThreads, expectedCount) {
  if (expectedCount === null) {
    return;
  }

  if (unresolvedThreads.length !== expectedCount) {
    throw new Error(
      `Expected ${expectedCount} unresolved review thread(s), found ${unresolvedThreads.length}.`
    );
  }
}

async function main() {
  const configuration = getConfiguration();
  const threads = configuration.inputPath
    ? loadReviewThreadsFromFile(configuration.inputPath)
    : await fetchAllReviewThreads(configuration);
  const unresolvedThreads = extractUnresolvedThreads(threads);
  const repository = `${configuration.owner}/${configuration.repo}`;
  validateExpectedCount(unresolvedThreads, configuration.expectedCount);
  process.stdout.write(
    formatOutput(repository, configuration.prNumber, unresolvedThreads, configuration.outputFormat)
  );
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}

module.exports = {
  DEFAULT_PR_NUMBER,
  DEFAULT_REPOSITORY,
  buildReviewThreadsQuery,
  extractUnresolvedThreads,
  extractThreadsFromSnapshot,
  formatOutput,
  formatThreadContent,
  formatUnresolvedThreadsAsJson,
  formatUnresolvedThreadsAsMarkdown,
  fetchAllReviewThreads,
  formatUnresolvedThreadsReport,
  getConfiguration,
  loadReviewThreadsFromFile,
  normalizeBody,
  parseCommandLineArguments,
  requestGraphql,
  validateExpectedCount,
};
