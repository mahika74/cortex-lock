export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function makeApi(operatorKey, reviewerKey = "") {
  return async (
    path,
    { method = "GET", body, reviewer = false, signal } = {},
  ) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 35000);
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    try {
      const response = await fetch("/api" + path, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(reviewer
            ? { "X-Reviewer-Key": reviewerKey }
            : { "X-Operator-Key": operatorKey }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal: controller.signal,
        cache: "no-store",
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const code =
          data?.error?.code ||
          (typeof data?.detail === "string"
            ? data.detail
            : `HTTP_${response.status}`);
        const message =
          response.status === 401
            ? "The access key was not accepted. Check your connection settings."
            : [502, 503, 504].includes(response.status)
              ? "Cannot reach the backend. Keep the Python server running on port 8000."
              : code.replaceAll("_", " ");
        throw new ApiError(message, code, response.status);
      }
      return data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error.name === "AbortError")
        throw new ApiError(
          "Request timed out or was cancelled. Refresh the task before retrying a write.",
          "REQUEST_TIMEOUT",
          0,
        );
      throw new ApiError(
        "Cannot reach the backend. Keep the Python server running on port 8000.",
        "BACKEND_UNREACHABLE",
        0,
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  };
}
