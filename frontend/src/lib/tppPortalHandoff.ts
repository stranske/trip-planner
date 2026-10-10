import type { WorkspaceProposalHandoffResponse } from "../api/workspace";

/** Submit a native browser form so TPP can set its own short-lived handoff cookie. */
export function submitTppPortalHandoff(
  handoff: WorkspaceProposalHandoffResponse,
  documentRef: Document = document
): void {
  const form = documentRef.createElement("form");
  form.method = "POST";
  form.enctype = "application/x-www-form-urlencoded";
  form.acceptCharset = "UTF-8";
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
  try {
    form.submit();
  } catch (error) {
    // Keep a successful form attached while the browser schedules navigation.
    // Failed submissions must not leave traveler facts in the page.
    form.remove();
    throw error;
  }
}
