import { ApiClientError, createApiClientError } from "./errors";

type JsonRequestOptions = RequestInit & {
  path: string;
};

function resolveRequestUrl(path: string): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configuredBaseUrl) {
    return path;
  }

  return new URL(path, `${configuredBaseUrl.replace(/\/+$/, "")}/`).toString();
}

export async function fetchJson<T>({ path, headers, ...init }: JsonRequestOptions): Promise<T> {
  const normalizedHeaders = new Headers(headers);
  normalizedHeaders.set("Accept", "application/json");
  const requestUrl = resolveRequestUrl(path);

  const response = await fetch(requestUrl, {
    ...init,
    headers: normalizedHeaders,
  });

  if (!response.ok) {
    throw await createApiClientError(requestUrl, response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const responseText = await response.text();
  if (!responseText) {
    return undefined as T;
  }

  try {
    return JSON.parse(responseText) as T;
  } catch (error) {
    throw new ApiClientError(`Response from ${requestUrl} was not valid JSON.`, {
      path: requestUrl,
      status: response.status,
      statusText: response.statusText,
      cause: error,
    });
  }
}
