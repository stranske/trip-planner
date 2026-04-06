import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import url from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

test("planner bundle passes JS type checking against orchestration contracts", async (t) => {
  let result;
  try {
    result = await execFileAsync("tsc", ["-p", "tsconfig.planner.json"], {
      cwd: repoRoot,
    });
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      t.skip("TypeScript compiler is not available in this environment.");
      return;
    }
    throw error;
  }

  assert.equal(result.stdout, "");
  assert.equal(result.stderr, "");
});
