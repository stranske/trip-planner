import { ApiClientError, createApiClientError } from "./errors";

type JsonRequestOptions = RequestInit & {
  path: string;
};

const HEALTH_RETRY_STATUSES = new Set([502, 503, 504]);
const HEALTH_RETRY_ATTEMPTS = 3;
const HEALTH_RETRY_DELAY_MS = 250;
// Bound each cold-start health probe so a backend that hangs (rather than
// returning 502/503/504) still consumes the retry budget and surfaces a
// bounded error instead of leaving the loading UI pending indefinitely.
const HEALTH_RETRY_TIMEOUT_MS = 5000;

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

async function fetchWithTimeout(
  requestUrl: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  // Without AbortController support (or an already-supplied signal) fall back
  // to a plain fetch so non-browser callers keep working.
  if (
    !timeoutMs ||
    typeof AbortController === "undefined" ||
    init.signal ||
    (typeof window !== "undefined" && fetch !== window.fetch)
  ) {
    return fetch(requestUrl, init);
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);
  try {
    return await fetch(requestUrl, { ...init, signal: controller.signal });
  } catch (error) {
    if (
      error instanceof TypeError &&
      String(error.message).includes("instance of AbortSignal")
    ) {
      return fetch(requestUrl, init);
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
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
      const response = retryEnabled
        ? await fetchWithTimeout(requestUrl, init, HEALTH_RETRY_TIMEOUT_MS)
        : await fetch(requestUrl, init);
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
