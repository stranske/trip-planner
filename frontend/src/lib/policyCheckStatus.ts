type PolicyCheckLifecycle = {
  state: "pending" | "deferred" | "running" | "failed" | "completed-with-follow-up" | "approval-ready";
  summary: string;
};

export function policyCheckStatusMessage(lifecycle: PolicyCheckLifecycle): string {
  switch (lifecycle.state) {
    case "failed":
      return `Policy check failed: ${lifecycle.summary}`;
    case "pending":
    case "deferred":
    case "running":
      return `Policy check pending: ${lifecycle.summary}`;
    default:
      return `Policy check completed: ${lifecycle.summary}`;
  }
}
