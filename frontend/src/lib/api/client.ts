import { ApiClientError, createApiClientError } from "./errors";

type JsonRequestOptions = RequestInit & {
  path: string;
};

const HEALTH_RETRY_STATUSES = new Set([502, 503, 504]);
const HEALTH_RETRY_ATTEMPTS = 3;
const HEALTH_RETRY_DELAY_MS = 250;

function resolveRequestUrl(path: string): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configuredBaseUrl) {
    return path;
  }

  return new URL(path, `${configuredBaseUrl.replace(/\/+$/, "")}/`).toString();
}

function isHealthProbe(path: string, method?: string): boolean {
  return path === "/api/health" && (!method || method.toUpperCase() === "GET");
}

function shouldRetryHealthProbe(error: unknown): boolean {
  return error instanceof TypeError || error instanceof DOMException;
}

function retryDelay(attemptIndex: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, HEALTH_RETRY_DELAY_MS * attemptIndex);
  });
}

async function fetchWithHealthRetry(
  requestUrl: string,
  init: RequestInit,
  retryEnabled: boolean
): Promise<Response> {
  const attemptCount = retryEnabled ? HEALTH_RETRY_ATTEMPTS : 1;
  let lastError: unknown;

  for (let attempt = 1; attempt <= attemptCount; attempt += 1) {
    try {
      const response = await fetch(requestUrl, init);
      if (
        retryEnabled &&
        attempt < attemptCount &&
        HEALTH_RETRY_STATUSES.has(response.status)
      ) {
        await retryDelay(attempt);
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (!retryEnabled || attempt >= attemptCount || !shouldRetryHealthProbe(error)) {
        throw error;
      }
      await retryDelay(attempt);
    }
  }

  throw lastError;
}

export async function fetchJson<T>({ path, headers, ...init }: JsonRequestOptions): Promise<T> {
  const normalizedHeaders = new Headers(headers);
  normalizedHeaders.set("Accept", "application/json");
  const requestUrl = resolveRequestUrl(path);

  const response = await fetchWithHealthRetry(
    requestUrl,
    {
      ...init,
      headers: normalizedHeaders,
    },
    isHealthProbe(path, init.method)
  );

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
