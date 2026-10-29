// One request per action: no retries and no alternate provider or API address.
export const TIMEOUTS = Object.freeze({ read: 15000, write: 25000, chat: 75000 });

export class ApiError extends Error {
  constructor(code, status = null) {
    super("API request could not be completed.");
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export function createApiClient(baseUrl, fetchImpl = globalThis.fetch, timeouts = TIMEOUTS) {
  const base = new URL(baseUrl);
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password
      || base.search || base.hash || base.pathname !== '/') {
    throw new ApiError("invalid_api_configuration");
  }
  return async function request(path, { method = "GET", body, kind = "read" } = {}) {
    if (!path.startsWith("/api/") || path.includes("?") || path.includes("#")
        || !Object.hasOwn(timeouts, kind)) throw new ApiError("invalid_api_configuration");
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeouts[kind]);
    try {
      const response = await fetchImpl(`${base.origin}${path}`, {
        method,
        signal: controller.signal,
        credentials: "omit",
        cache: "no-store",
        headers: body === undefined ? { Accept: "application/json" }
          : { Accept: "application/json", "Content-Type": "application/json" },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (response.status === 204 && response.ok) return null;
      let payload;
      try { payload = await response.json(); } catch {
        throw new ApiError(response.ok ? "invalid_response" : "http_error", response.status);
      }
      if (!response.ok) {
        const candidate = payload?.detail?.code;
        const code = typeof candidate === "string" && /^[a-z_]{1,64}$/.test(candidate)
          ? candidate : "http_error";
        throw new ApiError(code, response.status);
      }
      return payload;
    } catch (error) {
      if (timedOut) throw new ApiError("client_timeout");
      if (error instanceof ApiError) throw error;
      throw new ApiError("network_error");
    } finally {
      clearTimeout(timer);
    }
  };
}
