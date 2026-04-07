type ApiClientErrorOptions = {
  path: string;
  status?: number;
  statusText?: string;
  cause?: unknown;
};

export class ApiClientError extends Error {
  readonly path: string;
  readonly status?: number;
  readonly statusText?: string;
  readonly cause?: unknown;

  constructor(message: string, options: ApiClientErrorOptions) {
    super(message);
    this.name = "ApiClientError";
    this.path = options.path;
    this.status = options.status;
    this.statusText = options.statusText;
    this.cause = options.cause;
  }
}

export async function createApiClientError(path: string, response: Response): Promise<ApiClientError> {
  const fallbackMessage = `Request to ${path} failed with status ${response.status}`;
  let message = fallbackMessage;

  try {
    const payload = (await response.clone().json()) as { detail?: string; message?: string };
    message = payload.detail ?? payload.message ?? fallbackMessage;
  } catch {
    const text = await response.clone().text();
    if (text.trim().length > 0) {
      message = text.trim();
    }
  }

  return new ApiClientError(message, {
    path,
    status: response.status,
    statusText: response.statusText,
  });
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    return error.message;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
}
