import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const {
  buildGhPrCreateArgs,
  combineCommandOutput,
  doesCreatedPullRequestMatchFollowUpPr,
  executeManifestGroups,
  extractCreatedPullRequestUrl,
  formatExecutionReport,
  isExistingPullRequestOutcome,
  loadManifest,
  normalizePullRequestUrl,
  parseCliArguments,
  resolveManifestRelativePath,
  runGhPrCreate,
  selectManifestGroups,
  validateManifestGroup,
  writeExecutionResults,
} = require(path.join(repoRoot, "scripts/create_follow_up_prs_from_manifest.js"));

test("parseCliArguments accepts manifest execution options", () => {
  const options = parseCliArguments([
    "--manifest",
    ".tmp/generated/manifest.json",
    "--execute",
    "--enforce-created-pr-match",
    "--format",
    "json",
    "--follow-up-pr",
    "https://github.com/stranske/trip-planner/pull/581",
    "--group-index",
    "2",
    "--write-results",
    ".tmp/generated/results.json",
  ]);

  assert.equal(options.manifestPath, path.resolve(".tmp/generated/manifest.json"));
  assert.equal(options.execute, true);
  assert.equal(options.enforceCreatedPrMatch, true);
  assert.equal(options.outputFormat, "json");
  assert.equal(options.followUpPr, "https://github.com/stranske/trip-planner/pull/581");
  assert.equal(options.groupIndex, 2);
  assert.equal(options.resultsPath, ".tmp/generated/results.json");
});

test("loadManifest rejects malformed manifests", () => {
  assert.throws(
    () =>
      loadManifest("manifest.json", {
        readFileSync: () => JSON.stringify({ artifactsDir: ".tmp" }),
      }),
    /must contain a "groups" array/
  );
});

test("validateManifestGroup reports missing execution fields", () => {
  assert.deepEqual(validateManifestGroup({}, 0), [
    "Group 1 is missing followUpPr.",
    "Group 1 is missing title.",
    "Group 1 is missing baseBranch.",
    "Group 1 is missing headBranch.",
    "Group 1 is missing bodyFilePath.",
  ]);
});

test("validateManifestGroup reports the manifest group number when present", () => {
  assert.deepEqual(validateManifestGroup({ manifestGroupNumber: 4 }, 0), [
    "Group 4 is missing followUpPr.",
    "Group 4 is missing title.",
    "Group 4 is missing baseBranch.",
    "Group 4 is missing headBranch.",
    "Group 4 is missing bodyFilePath.",
  ]);
});

test("selectManifestGroups can isolate a specific follow-up PR", () => {
  const groups = selectManifestGroups(
    {
      groups: [
        { followUpPr: "https://github.com/stranske/trip-planner/pull/581" },
        { followUpPr: "https://github.com/stranske/trip-planner/pull/582" },
      ],
    },
    {
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
      groupIndex: null,
    }
  );

  assert.equal(groups.length, 1);
  assert.equal(groups[0].followUpPr, "https://github.com/stranske/trip-planner/pull/582");
  assert.equal(groups[0].manifestGroupNumber, 2);
});

test("buildGhPrCreateArgs returns a non-shell command argv list", () => {
  assert.deepEqual(
    buildGhPrCreateArgs({
      baseBranch: "main",
      headBranch: "codex/fix-thread-1",
      title: "Address PR #178 fix threads for follow-up PR #581",
      bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
    }),
    [
      "pr",
      "create",
      "--base",
      "main",
      "--head",
      "codex/fix-thread-1",
      "--title",
      "Address PR #178 fix threads for follow-up PR #581",
      "--body-file",
      ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
    ]
  );
});

test("runGhPrCreate captures stdout, stderr, and exit status from spawnSync", () => {
  const result = runGhPrCreate(["pr", "create"], {
    spawnSync: (command, args, options) => {
      assert.equal(command, "gh");
      assert.deepEqual(args, ["pr", "create"]);
      assert.deepEqual(options, { encoding: "utf8" });
      return {
        status: 1,
        stdout: "stdout line\n",
        stderr: "stderr line\n",
      };
    },
  });

  assert.deepEqual(result, {
    status: 1,
    stdout: "stdout line",
    stderr: "stderr line",
  });
});

test("extractCreatedPullRequestUrl returns the created PR URL from gh output", () => {
  assert.equal(
    extractCreatedPullRequestUrl(
      "Creating pull request for codex/fix-thread-1 into main in stranske/trip-planner\nhttps://github.com/stranske/trip-planner/pull/622\n"
    ),
    "https://github.com/stranske/trip-planner/pull/622"
  );
  assert.equal(extractCreatedPullRequestUrl("created successfully"), null);
});

test("combineCommandOutput joins stdout and stderr without blank lines", () => {
  assert.equal(combineCommandOutput("created", "warning"), "created\nwarning");
  assert.equal(combineCommandOutput("", "warning"), "warning");
});

test("normalizePullRequestUrl trims whitespace and trailing slashes", () => {
  assert.equal(
    normalizePullRequestUrl(" https://github.com/stranske/trip-planner/pull/622/ "),
    "https://github.com/stranske/trip-planner/pull/622"
  );
  assert.equal(normalizePullRequestUrl("   "), null);
});

test("doesCreatedPullRequestMatchFollowUpPr compares normalized PR URLs", () => {
  assert.equal(
    doesCreatedPullRequestMatchFollowUpPr(
      "https://github.com/stranske/trip-planner/pull/622/",
      "https://github.com/stranske/trip-planner/pull/622"
    ),
    true
  );
  assert.equal(
    doesCreatedPullRequestMatchFollowUpPr(
      "https://github.com/stranske/trip-planner/pull/581",
      "https://github.com/stranske/trip-planner/pull/622"
    ),
    false
  );
  assert.equal(
    doesCreatedPullRequestMatchFollowUpPr(null, "https://github.com/stranske/trip-planner/pull/622"),
    null
  );
});

test("isExistingPullRequestOutcome recognizes already-existing PR output with a URL", () => {
  assert.equal(
    isExistingPullRequestOutcome(
      1,
      "a pull request already exists for branch\nhttps://github.com/stranske/trip-planner/pull/622",
      "https://github.com/stranske/trip-planner/pull/622"
    ),
    true
  );
  assert.equal(
    isExistingPullRequestOutcome(
      1,
      "a pull request already exists for branch",
      null
    ),
    false
  );
});

test("resolveManifestRelativePath resolves paths relative to the manifest location", () => {
  assert.equal(
    resolveManifestRelativePath(
      path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      "pr-178-fix-group-1-body.md"
    ),
    path.resolve(".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md")
  );
  assert.equal(
    resolveManifestRelativePath(
      path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      "/tmp/pr-178-fix-group-1-body.md"
    ),
    "/tmp/pr-178-fix-group-1-body.md"
  );
});

test("executeManifestGroups supports dry-run mode without invoking gh", () => {
  const writes = [];
  const report = executeManifestGroups(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: false,
      followUpPr: null,
      groupIndex: null,
      resultsPath: "created-prs.json",
    },
    {
      readFileSync: () =>
        JSON.stringify({
          groups: [
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/581",
              title: "Address PR #178 fix threads for follow-up PR #581",
              baseBranch: "main",
              headBranch: "codex/fix-thread-1",
              bodyFilePath: "pr-178-fix-group-1-body.md",
            },
          ],
        }),
      statSync: (bodyFilePath) => {
        assert.equal(
          bodyFilePath,
          path.resolve(".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md")
        );
        return { isFile: () => true };
      },
      execFileSync: () => {
        throw new Error("gh should not be called during dry run");
      },
      writeFileSync: (filePath, content, encoding) => {
        writes.push({ filePath, content, encoding });
      },
    }
  );

  assert.equal(report.execute, false);
  assert.equal(report.groupCount, 1);
  assert.equal(report.resultsPath, path.resolve(".tmp/pr-thread-payloads/created-prs.json"));
  assert.equal(report.results[0].manifestGroupNumber, 1);
  assert.equal(report.results[0].mode, "dry-run");
  assert.equal(
    report.results[0].bodyFilePath,
    path.resolve(".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md")
  );
  assert.match(report.results[0].command, /^gh pr create --base main --head codex\/fix-thread-1/);
  assert.equal(writes.length, 1);
  assert.equal(writes[0].filePath, path.resolve(".tmp/pr-thread-payloads/created-prs.json"));
  assert.equal(writes[0].encoding, "utf8");
  assert.match(writes[0].content, /"resultsPath":/);
});

test("executeManifestGroups invokes gh for selected groups in execute mode", () => {
  const calls = [];
  const report = executeManifestGroups(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: true,
      followUpPr: "https://github.com/stranske/trip-planner/pull/582",
      groupIndex: null,
    },
    {
      readFileSync: () =>
        JSON.stringify({
          groups: [
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/581",
              title: "Ignore me",
              baseBranch: "main",
              headBranch: "codex/fix-thread-1",
              bodyFilePath: "pr-178-fix-group-1-body.md",
            },
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/582",
              title: "Address PR #178 fix threads for follow-up PR #582",
              baseBranch: "release/next",
              headBranch: "codex/fix-thread-2",
              bodyFilePath: "pr-178-fix-group-2-body.md",
            },
          ],
        }),
      statSync: (bodyFilePath) => {
        assert.equal(
          bodyFilePath,
          path.resolve(".tmp/pr-thread-payloads/pr-178-fix-group-2-body.md")
        );
        return { isFile: () => true };
      },
      spawnSync: (command, args, execOptions) => {
        calls.push({ command, args, execOptions });
        return {
          status: 0,
          stdout: "https://github.com/stranske/trip-planner/pull/622\n",
          stderr: "",
        };
      },
    }
  );

  assert.equal(calls.length, 1);
  assert.equal(calls[0].command, "gh");
  assert.deepEqual(calls[0].args, [
    "pr",
    "create",
    "--base",
    "release/next",
    "--head",
    "codex/fix-thread-2",
    "--title",
    "Address PR #178 fix threads for follow-up PR #582",
    "--body-file",
    path.resolve(".tmp/pr-thread-payloads/pr-178-fix-group-2-body.md"),
  ]);
  assert.deepEqual(calls[0].execOptions, { encoding: "utf8" });
  assert.equal(report.results[0].manifestGroupNumber, 2);
  assert.equal(report.results[0].output, "https://github.com/stranske/trip-planner/pull/622");
  assert.equal(
    report.results[0].createdPullRequestUrl,
    "https://github.com/stranske/trip-planner/pull/622"
  );
  assert.equal(report.results[0].createdPullRequestMatchesFollowUpPr, false);
});

test("executeManifestGroups preserves manifest numbering after selecting a later group index", () => {
  const report = executeManifestGroups(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: false,
      followUpPr: null,
      groupIndex: 2,
    },
    {
      readFileSync: () =>
        JSON.stringify({
          groups: [
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/581",
              title: "Ignore me",
              baseBranch: "main",
              headBranch: "codex/fix-thread-1",
              bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
            },
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/582",
              title: "Address PR #178 fix threads for follow-up PR #582",
              baseBranch: "main",
              headBranch: "codex/fix-thread-2",
              bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-2-body.md",
            },
          ],
        }),
      statSync: () => ({ isFile: () => true }),
    }
  );

  assert.equal(report.groupCount, 1);
  assert.equal(report.results[0].groupNumber, 1);
  assert.equal(report.results[0].manifestGroupNumber, 2);
});

test("executeManifestGroups fails when the selected body file is missing", () => {
  assert.throws(
    () =>
      executeManifestGroups(
        {
          manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
          execute: false,
          followUpPr: null,
          groupIndex: null,
        },
        {
          readFileSync: () =>
            JSON.stringify({
              groups: [
                {
                  followUpPr: "https://github.com/stranske/trip-planner/pull/581",
                  title: "Address PR #178 fix threads for follow-up PR #581",
                  baseBranch: "main",
                  headBranch: "codex/fix-thread-1",
                  bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
                },
              ],
            }),
          statSync: () => {
            throw new Error("ENOENT");
          },
        }
      ),
    /body file does not exist/
  );
});

test("executeManifestGroups fails when the selected body path is not a regular file", () => {
  assert.throws(
    () =>
      executeManifestGroups(
        {
          manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
          execute: false,
          followUpPr: null,
          groupIndex: null,
        },
        {
          readFileSync: () =>
            JSON.stringify({
              groups: [
                {
                  followUpPr: "https://github.com/stranske/trip-planner/pull/581",
                  title: "Address PR #178 fix threads for follow-up PR #581",
                  baseBranch: "main",
                  headBranch: "codex/fix-thread-1",
                  bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
                },
              ],
            }),
          statSync: () => ({ isFile: () => false }),
        }
      ),
    /body file is not a regular file/
  );
});

test("executeManifestGroups fails when gh output does not include a PR URL", () => {
  assert.throws(
    () =>
      executeManifestGroups(
        {
          manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
          execute: true,
          followUpPr: null,
          groupIndex: null,
        },
        {
          readFileSync: () =>
            JSON.stringify({
              groups: [
                {
                  followUpPr: "https://github.com/stranske/trip-planner/pull/581",
                  title: "Address PR #178 fix threads for follow-up PR #581",
                  baseBranch: "main",
                  headBranch: "codex/fix-thread-1",
                  bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
                },
              ],
            }),
          statSync: () => ({ isFile: () => true }),
          spawnSync: () => ({
            status: 0,
            stdout: "created successfully\n",
            stderr: "",
          }),
        }
      ),
    /did not include a pull request URL/
  );
});

test("executeManifestGroups accepts an already-existing PR URL reported on stderr", () => {
  const report = executeManifestGroups(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: true,
      followUpPr: null,
      groupIndex: null,
    },
    {
      readFileSync: () =>
        JSON.stringify({
          groups: [
            {
              followUpPr: "https://github.com/stranske/trip-planner/pull/622",
              title: "Address PR #178 fix threads for follow-up PR #622",
              baseBranch: "main",
              headBranch: "codex/fix-thread-1",
              bodyFilePath: "pr-178-fix-group-1-body.md",
            },
          ],
        }),
      statSync: () => ({ isFile: () => true }),
      spawnSync: () => ({
        status: 1,
        stdout: "",
        stderr:
          "a pull request already exists for branch \"codex/fix-thread-1\"\nhttps://github.com/stranske/trip-planner/pull/622\n",
      }),
    }
  );

  assert.equal(report.results[0].createdPullRequestUrl, "https://github.com/stranske/trip-planner/pull/622");
  assert.equal(report.results[0].createdPullRequestAlreadyExisted, true);
  assert.equal(report.results[0].commandExitStatus, 1);
  assert.equal(report.results[0].createdPullRequestMatchesFollowUpPr, true);
});

test("executeManifestGroups fails on nonzero gh exit status without an existing PR URL", () => {
  assert.throws(
    () =>
      executeManifestGroups(
        {
          manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
          execute: true,
          followUpPr: null,
          groupIndex: null,
        },
        {
          readFileSync: () =>
            JSON.stringify({
              groups: [
                {
                  followUpPr: "https://github.com/stranske/trip-planner/pull/581",
                  title: "Address PR #178 fix threads for follow-up PR #581",
                  baseBranch: "main",
                  headBranch: "codex/fix-thread-1",
                  bodyFilePath: "pr-178-fix-group-1-body.md",
                },
              ],
            }),
          statSync: () => ({ isFile: () => true }),
          spawnSync: () => ({
            status: 1,
            stdout: "",
            stderr: "HTTP 422: Validation Failed\n",
          }),
        }
      ),
    /gh pr create failed with exit code 1/
  );
});

test("executeManifestGroups can enforce that the created PR matches the follow-up PR", () => {
  assert.throws(
    () =>
      executeManifestGroups(
        {
          manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
          execute: true,
          enforceCreatedPrMatch: true,
          followUpPr: null,
          groupIndex: null,
        },
        {
          readFileSync: () =>
            JSON.stringify({
              groups: [
                {
                  followUpPr: "https://github.com/stranske/trip-planner/pull/581",
                  title: "Address PR #178 fix threads for follow-up PR #581",
                  baseBranch: "main",
                  headBranch: "codex/fix-thread-1",
                  bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
                },
              ],
            }),
          statSync: () => ({ isFile: () => true }),
          spawnSync: () => ({
            status: 0,
            stdout: "https://github.com/stranske/trip-planner/pull/622\n",
            stderr: "",
          }),
        }
      ),
    /does not match follow-up PR/
  );
});

test("formatExecutionReport emits readable dry-run output", () => {
  const report = formatExecutionReport(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: false,
      resultsPath: path.resolve(".tmp/pr-thread-payloads/created-prs.json"),
      groupCount: 1,
      results: [
        {
          groupNumber: 1,
          manifestGroupNumber: 3,
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          mode: "dry-run",
          baseBranch: "main",
          headBranch: "codex/fix-thread-1",
          bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
          command:
            "gh pr create --base main --head codex/fix-thread-1 --title example --body-file .tmp/body.md",
          output: null,
        },
      ],
    },
    "text"
  );

  assert.match(report, /# Follow-up PR Dry Run/);
  assert.match(report, /Selected Groups: 1/);
  assert.match(report, /Results File: `.*created-prs\.json`/);
  assert.match(report, /Manifest Group 3/);
  assert.match(report, /Mode: dry-run/);
  assert.match(report, /Command: `gh pr create --base main --head codex\/fix-thread-1/);
});

test("writeExecutionResults persists the execution report as JSON", () => {
  const writes = [];
  const report = {
    manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
    execute: true,
    resultsPath: path.resolve(".tmp/pr-thread-payloads/created-prs.json"),
    groupCount: 1,
    results: [
      {
        manifestGroupNumber: 1,
        followUpPr: "https://github.com/stranske/trip-planner/pull/581",
        createdPullRequestUrl: "https://github.com/stranske/trip-planner/pull/622",
      },
    ],
  };

  writeExecutionResults(report, report.resultsPath, {
    writeFileSync: (filePath, content, encoding) => {
      writes.push({ filePath, content, encoding });
    },
  });

  assert.equal(writes.length, 1);
  assert.equal(writes[0].filePath, report.resultsPath);
  assert.equal(writes[0].encoding, "utf8");
  assert.deepEqual(JSON.parse(writes[0].content), report);
});

test("formatExecutionReport includes the created PR URL when available", () => {
  const report = formatExecutionReport(
    {
      manifestPath: path.resolve(".tmp/pr-thread-payloads/manifest.json"),
      execute: true,
      groupCount: 1,
      results: [
        {
          groupNumber: 1,
          manifestGroupNumber: 1,
          followUpPr: "https://github.com/stranske/trip-planner/pull/581",
          mode: "execute",
          baseBranch: "main",
          headBranch: "codex/fix-thread-1",
          bodyFilePath: ".tmp/pr-thread-payloads/pr-178-fix-group-1-body.md",
          command:
            "gh pr create --base main --head codex/fix-thread-1 --title example --body-file .tmp/body.md",
          output: "https://github.com/stranske/trip-planner/pull/622",
          createdPullRequestUrl: "https://github.com/stranske/trip-planner/pull/622",
          createdPullRequestAlreadyExisted: true,
          commandExitStatus: 1,
          createdPullRequestMatchesFollowUpPr: false,
        },
      ],
    },
    "text"
  );

  assert.match(report, /Created PR: https:\/\/github\.com\/stranske\/trip-planner\/pull\/622/);
  assert.match(report, /Created PR Already Existed: yes/);
  assert.match(report, /Command Exit Status: 1/);
  assert.match(report, /Created PR Matches Follow-up PR: no/);
});
