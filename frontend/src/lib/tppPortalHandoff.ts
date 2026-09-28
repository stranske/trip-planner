import type { WorkspaceProposalHandoffResponse } from "../api/workspace";

/** Submit a native browser form so TPP can set its own short-lived handoff cookie. */
export function submitTppPortalHandoff(
  handoff: WorkspaceProposalHandoffResponse,
  documentRef: Document = document
): void {
  const form = documentRef.createElement("form");
  form.method = "POST";
  form.action = handoff.action_url;
  form.hidden = true;

  for (const [name, value] of Object.entries(handoff.fields)) {
    const input = documentRef.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.append(input);
  }

  documentRef.body.append(form);
  form.submit();
}
