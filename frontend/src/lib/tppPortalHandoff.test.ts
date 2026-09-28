import { describe, expect, it, vi } from "vitest";

import { submitTppPortalHandoff } from "./tppPortalHandoff";

describe("submitTppPortalHandoff", () => {
  it("posts fields in the form body without placing traveler data in the URL", () => {
    const submit = vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(() => {});

    submitTppPortalHandoff({
      action_url: "https://tpp.example/portal/handoff",
      method: "POST",
      fields: {
        traveler_name: "Morgan Planner",
        business_purpose: "Client planning",
      },
      handoff: {
        status: "prepared",
        manager_submission_status: "unknown",
        manager_decision: null,
      },
    });

    const form = document.body.querySelector("form");
    expect(form).not.toBeNull();
    expect(form?.method).toBe("post");
    expect(form?.action).toBe("https://tpp.example/portal/handoff");
    expect(form?.action).not.toContain("Morgan");
    expect(new FormData(form as HTMLFormElement).get("traveler_name")).toBe("Morgan Planner");
    expect(submit).toHaveBeenCalledOnce();

    form?.remove();
    submit.mockRestore();
  });
});
