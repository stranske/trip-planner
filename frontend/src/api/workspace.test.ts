import { afterEach, expect, it, vi } from "vitest";

import { fetchWorkspace, reoptimizeWorkspaceProposal } from "./workspace";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("loads the saved workspace from a configured API origin with session credentials", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/base/");
  const workspacePayload = {
    trip_record: {
      trip: {
        trip_id: "trip:kyoto",
      },
    },
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(workspacePayload),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(fetchWorkspace("trip:kyoto")).resolves.toEqual(workspacePayload);

  expect(fetchMock).toHaveBeenCalledWith(
    "https://api.example.test/api/workspace/trip:kyoto",
    expect.objectContaining({ credentials: "include" })
  );
});

it("posts comparable and justification refs to reoptimize the workspace proposal", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/base/");
  const proposalState = {
    proposal_state_id: "proposal-state:trip:kyoto",
    trip_id: "trip:kyoto",
    proposal_id: "proposal:trip:kyoto",
    proposal_version: "proposal-v3",
    scenario_id: "scenario:kyoto-1",
    execution_id: "exec-1",
    submission_status: "succeeded",
    evaluation_status: "succeeded",
    proposal: { proposal_id: "proposal:trip:kyoto" },
    evaluation: { evaluation_result: null },
    follow_up: {
      status: "reoptimized",
      path: "reoptimization",
      title: "Reoptimization path required",
      summary: "Narrow candidate search around policy-preferred alternatives",
      recommended_action: "reoptimize",
      recommended_label: "Reoptimize plan",
      reoptimization_plan: {
        proposal_id: "proposal:trip:kyoto",
        evaluation_id: "eval-1",
        reaction_kind: "narrow_candidates",
        target_label: "compliant_first",
        comparison_outcome: "preferred",
        target_title: "Narrow candidate search around policy-preferred alternatives",
        candidate_categories: ["lodging"],
      },
    },
    summary: {
      evaluation_result_status: "non_compliant",
      follow_up_status: "reoptimized",
    },
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify({ proposal_state: proposalState, summary: proposalState.summary }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const result = await reoptimizeWorkspaceProposal("trip:kyoto", {
    comparable_refs: { lodging: ["lodging-alt-2"] },
    justification_refs: { lodging: ["fare-policy"] },
  });

  expect(result).toEqual(proposalState);
  expect(fetchMock).toHaveBeenCalledWith(
    "https://api.example.test/api/workspace/trip:kyoto/proposal/reoptimize",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        comparable_refs: { lodging: ["lodging-alt-2"] },
        justification_refs: { lodging: ["fare-policy"] },
      }),
    })
  );
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(new Headers(init.headers).get("content-type")).toBe("application/json");
});
