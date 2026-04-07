import { ApiClientError, createApiClientError } from "./errors";

type JsonRequestOptions = RequestInit & {
  path: string;
};

export async function fetchJson<T>({ path, headers, ...init }: JsonRequestOptions): Promise<T> {
  const normalizedHeaders = new Headers(headers);
  normalizedHeaders.set("Accept", "application/json");

  const response = await fetch(path, {
    ...init,
    headers: normalizedHeaders,
  });

  if (!response.ok) {
    throw await createApiClientError(path, response);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiClientError(`Response from ${path} was not valid JSON.`, {
      path,
      status: response.status,
      statusText: response.statusText,
      cause: error,
    });
  }
}
