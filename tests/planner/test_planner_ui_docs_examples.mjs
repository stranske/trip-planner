import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import url from "node:url";

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

async function loadModule(relativePath) {
  const source = await fs.readFile(path.join(repoRoot, relativePath), "utf8");
  return import(`data:text/javascript,${encodeURIComponent(source)}`);
}

const {
  businessApprovalReadyReviewState,
  leisureFeedbackLoopState,
} = await loadModule("bundle/planner/mock-state.js");
const {
  POLICY_STATUS_COMPONENT_MAP,
  buildPlannerUiConsumptionExample,
  mapPolicyStateToUiComponents,
} = await loadModule("docs/scripts/planner_ui_consumption_example.js");

test("documentation consumption example summarizes planner sections from orchestration state", () => {
  const summary = buildPlannerUiConsumptionExample(leisureFeedbackLoopState);

  assert.equal(summary.summary.trip_id, "trip-leisure-lisbon-oct");
  assert.equal(summary.summary.mode, "leisure");
  assert.deepEqual(summary.sections, {
    outputs: 2,
    decisions: 1,
    options: 2,
    approval: false,
  });
  assert.equal(summary.approval.status, null);
  assert.deepEqual(summary.approval.mapped_components, []);
});

test("documentation policy mapping example reflects approval widgets for business review states", () => {
  const mapped = mapPolicyStateToUiComponents(businessApprovalReadyReviewState.policy_evaluation);

  assert.equal(mapped.status, "exception_required");
  assert.equal(mapped.posture_tone, "caution");
  assert.equal(mapped.readiness_label, "exception packet ready");
  assert.equal(mapped.blocking_failure_count, 0);
  assert.equal(mapped.approval_requirement_count, 2);
  assert.deepEqual(
    mapped.mapped_components,
    POLICY_STATUS_COMPONENT_MAP.exception_required.components
  );
});

test("documentation policy mapping example handles inactive approval state", () => {
  const mapped = mapPolicyStateToUiComponents(null);

  assert.deepEqual(mapped, {
    status: "inactive",
    posture_tone: "neutral",
    readiness_label: "not rendered",
    blocking_failure_count: 0,
    approval_requirement_count: 0,
    mapped_components: [],
  });
});
