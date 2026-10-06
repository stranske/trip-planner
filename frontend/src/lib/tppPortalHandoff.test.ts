import { afterEach, describe, expect, it, vi } from "vitest";

import { submitTppPortalHandoff } from "./tppPortalHandoff";

describe("submitTppPortalHandoff", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.querySelectorAll("form").forEach((form) => form.remove());
  });

  it("posts fields in the form body without placing traveler data in the URL", () => {
    let submittedForm: HTMLFormElement | undefined;
    const submit = vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(
      function (this: HTMLFormElement) {
        submittedForm = this;
        expect(this.isConnected).toBe(true);
      }
    );

    submitTppPortalHandoff({
      action_url: "https://tpp.example/portal/handoff",
      method: "POST",
      fields: {
        traveler_name: "Morgan José Planner",
        business_purpose: "Client planning & review = Q4",
      },
      handoff: {
        status: "prepared",
        manager_submission_status: "unknown",
        manager_decision: null,
      },
    });

    const form = submittedForm;
    expect(form).toBeDefined();
    expect(form?.method).toBe("post");
    expect(form?.enctype).toBe("application/x-www-form-urlencoded");
    expect(form?.acceptCharset).toBe("UTF-8");
    expect(form?.action).toBe("https://tpp.example/portal/handoff");
    expect(form?.action).not.toContain("Morgan");
    expect(new FormData(form as HTMLFormElement).get("traveler_name")).toBe("Morgan José Planner");
    expect(new FormData(form as HTMLFormElement).get("business_purpose")).toBe(
      "Client planning & review = Q4"
    );
    expect(submit).toHaveBeenCalledOnce();
    expect(document.body.querySelector("form")).toBe(form);
  });

  it("removes traveler fields when native form submission fails", () => {
    vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(() => {
      throw new Error("Navigation failed");
    });

    expect(() =>
      submitTppPortalHandoff({
        action_url: "https://tpp.example/portal/handoff",
        method: "POST",
        fields: { traveler_name: "Morgan Planner" },
        handoff: { status: "prepared" },
      })
    ).toThrow("Navigation failed");
    expect(document.body.querySelector("form")).toBeNull();
  });
});
