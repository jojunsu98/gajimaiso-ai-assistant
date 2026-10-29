/** Pure frontend regressions. All HTTP responses are local fakes; no backend or AI calls. */
import assert from "node:assert/strict";
import { monthToDate, parseInteger, shouldSendOnEnter, formatNumber, safeErrorMessage } from "../../frontend/app.js";
import { createApiClient, ApiError, TIMEOUTS } from "../../frontend/api.js";

const cases = [];
const test = (name, run) => cases.push({ name, run });

test("month uses representative day without timezone conversion", () => {
  assert.equal(monthToDate("2026-08"), "2026-08-01");
  assert.equal(monthToDate("2024-02"), "2024-02-01");
  assert.equal(monthToDate("0001-01"), "0001-01-01");
});
for (const value of ["", "2026-00", "2026-13", "2026-8", "26-08", "2026-08-01", "0000-01", "2026-08<script>"]) {
  test(`invalid month rejected: ${JSON.stringify(value)}`, () => assert.throws(() => monthToDate(value)));
}
test("negative and zero integer input stay exact", () => {
  assert.equal(parseInteger("-558"), -558);
  assert.equal(parseInteger("0"), 0);
  assert.equal(parseInteger(" -12 "), -12);
});
test("safe integer boundaries stay exact", () => {
  assert.equal(parseInteger(String(Number.MAX_SAFE_INTEGER)), Number.MAX_SAFE_INTEGER);
  assert.equal(parseInteger(String(Number.MIN_SAFE_INTEGER)), Number.MIN_SAFE_INTEGER);
});
for (const value of ["", " ", "1.5", "1.0", "1e3", "NaN", "Infinity", "1,234", "9007199254740992", "-9007199254740992"]) {
  test(`invalid or lossy integer rejected: ${JSON.stringify(value)}`, () => assert.throws(() => parseInteger(value)));
}
test("formatted numbers distinguish negative, zero and missing", () => {
  assert.match(formatNumber(-1234), /-1,234/);
  assert.equal(formatNumber(0), "0");
  assert.notEqual(formatNumber(null), formatNumber(0));
  assert.notEqual(formatNumber(undefined), formatNumber(0));
  assert.doesNotMatch(formatNumber(null), /NaN|undefined|null/);
});
test("Enter submits only without shift or Korean composition", () => {
  const event = { key: "Enter", shiftKey: false, isComposing: false, keyCode: 13 };
  assert.equal(shouldSendOnEnter(event), true);
  assert.equal(shouldSendOnEnter({ ...event, shiftKey: true }), false);
  assert.equal(shouldSendOnEnter({ ...event, isComposing: true }), false);
  assert.equal(shouldSendOnEnter({ ...event, keyCode: 229 }), false);
  assert.equal(shouldSendOnEnter({ ...event, key: "a" }), false);
  assert.equal(shouldSendOnEnter(event, true), false);
});

const base = "http://127.0.0.1:9876";
const fakeResponse = (status, payload) => ({
  status, ok: status >= 200 && status < 300,
  json: async () => payload,
});
const getError = async (run) => {
  try { await run(); } catch (error) { return error; }
  assert.fail("request should have failed");
};
test("each request category has a finite bounded timeout", () => {
  for (const kind of ["read", "write", "chat"]) {
    assert.equal(Number.isFinite(TIMEOUTS[kind]), true);
    assert.ok(TIMEOUTS[kind] > 0 && TIMEOUTS[kind] <= 120000);
  }
  assert.ok(TIMEOUTS.chat > TIMEOUTS.read);
});
test("chat targets only the configured backend with the API request contract", async () => {
  const calls = [];
  const expected = { conversation_id: "local-test-conversation", reply: "모의 답변", saved: true };
  const request = createApiClient(base, async (...args) => {
    calls.push(args);
    return fakeResponse(200, expected);
  });
  const body = { message: "테스트 질문", conversation_id: null };
  assert.deepEqual(await request("/api/chat", { method: "POST", body, kind: "chat" }), expected);
  assert.equal(calls.length, 1);
  const [url, options] = calls[0];
  assert.equal(url, `${base}/api/chat`);
  assert.equal(options.method, "POST");
  assert.deepEqual(JSON.parse(options.body), body);
  assert.equal(options.headers["Content-Type"], "application/json");
  assert.equal(Object.keys(options.headers).some((key) => key.toLowerCase() === "authorization"), false);
  assert.equal(options.credentials, "omit");
  assert.equal(options.cache, "no-store");
});
test("read request passes the actual payload without invented data", async () => {
  let seen;
  const expected = { items: [], count: 0 };
  const request = createApiClient(base, async (url, options) => {
    seen = { url, options };
    return fakeResponse(200, expected);
  });
  assert.deepEqual(await request("/api/data"), expected);
  assert.equal(seen.options.method, "GET");
  assert.equal(Object.hasOwn(seen.options, "body"), false);
});
test("204 deletion never parses JSON", async () => {
  let calls = 0;
  let parsed = false;
  const request = createApiClient(base, async () => {
    calls += 1;
    return { status: 204, ok: true, json: async () => { parsed = true; throw new Error("no body"); } };
  });
  assert.equal(await request("/api/data/changwon-net-2099-01", { method: "DELETE", kind: "write" }), null);
  assert.equal(parsed, false);
  assert.equal(calls, 1);
});
for (const [status, code] of [[422, "validation_error"], [409, "data_already_exists"], [404, "data_not_found"], [503, "database_unavailable"]]) {
  test(`HTTP ${status} carries status and displays safe local guidance`, async () => {
    let calls = 0;
    const request = createApiClient(base, async () => {
      calls += 1;
      return fakeResponse(status, { detail: { code, message: "DO_NOT_SHOW_INTERNAL_DETAILS" } });
    });
    const error = await getError(() => request("/api/data", { method: "POST", body: {}, kind: "write" }));
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, status);
    assert.equal(error.code, code);
    assert.equal(calls, 1);
    const message = safeErrorMessage(error);
    assert.equal(typeof message, "string");
    assert.ok(message.length > 0);
    assert.doesNotMatch(message, /DO_NOT_SHOW_INTERNAL_DETAILS|API request could not/);
  });
}
test("422 FastAPI validation arrays retain safe status guidance", async () => {
  const request = createApiClient(base, async () => fakeResponse(422, {
    detail: [{ loc: ["body", "value"], msg: "DO_NOT_SHOW_INTERNAL_DETAILS", input: "unsafe" }],
  }));
  const error = await getError(() => request("/api/data", { method: "POST", body: {}, kind: "write" }));
  assert.equal(error.status, 422);
  assert.equal(error.code, "http_error");
  assert.doesNotMatch(safeErrorMessage(error), /DO_NOT_SHOW_INTERNAL_DETAILS|unsafe/);
});
test("non-JSON server errors do not leak body or parser error", async () => {
  let calls = 0;
  const request = createApiClient(base, async () => {
    calls += 1;
    return { status: 503, ok: false, json: async () => { throw new Error("DO_NOT_SHOW_INTERNAL_DETAILS"); } };
  });
  const error = await getError(() => request("/api/data"));
  assert.equal(error.code, "http_error");
  assert.equal(error.status, 503);
  assert.equal(calls, 1);
  assert.doesNotMatch(error.message + safeErrorMessage(error), /DO_NOT_SHOW_INTERNAL_DETAILS/);
});
test("invalid successful JSON is a response error instead of made-up data", async () => {
  const request = createApiClient(base, async () => ({
    status: 200, ok: true, json: async () => { throw new Error("invalid JSON"); },
  }));
  const error = await getError(() => request("/api/data/summary"));
  assert.equal(error.code, "invalid_response");
  assert.equal(error.status, 200);
});
test("unknown or malformed server codes do not expose server details", async () => {
  const request = createApiClient(base, async () => fakeResponse(500, {
    detail: { code: "<script>DO_NOT_SHOW_INTERNAL_DETAILS</script>", message: "DO_NOT_SHOW_INTERNAL_DETAILS" },
  }));
  const error = await getError(() => request("/api/conversations"));
  assert.equal(error.code, "http_error");
  assert.doesNotMatch(safeErrorMessage(error), /script|DO_NOT_SHOW_INTERNAL_DETAILS/);
  assert.doesNotMatch(safeErrorMessage(new Error("DO_NOT_SHOW_INTERNAL_DETAILS")), /DO_NOT_SHOW_INTERNAL_DETAILS/);
});
test("network failure remains distinct and never retries a chat", async () => {
  let calls = 0;
  const request = createApiClient(base, async () => { calls += 1; throw new TypeError("DO_NOT_SHOW_INTERNAL_DETAILS"); });
  const error = await getError(() => request("/api/chat", { method: "POST", body: { message: "질문" }, kind: "chat" }));
  assert.equal(error.code, "network_error");
  assert.equal(error.status, null);
  assert.equal(calls, 1);
  assert.doesNotMatch(safeErrorMessage(error, { chat: true }), /DO_NOT_SHOW_INTERNAL_DETAILS/);
  assert.match(safeErrorMessage(error, { chat: true }), /이전 질문 목록/);
});
test("chat timeout aborts browser wait once and advises checking saved history", async () => {
  let calls = 0;
  let aborted = false;
  const request = createApiClient(base, (_url, options) => {
    calls += 1;
    return new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        aborted = true;
        reject(Object.assign(new Error("local timeout"), { name: "AbortError" }));
      }, { once: true });
    });
  }, { read: 10, write: 10, chat: 10 });
  const error = await getError(() => request("/api/chat", { method: "POST", body: { message: "질문" }, kind: "chat" }));
  assert.equal(aborted, true);
  assert.equal(error.code, "client_timeout");
  assert.equal(error.status, null);
  assert.equal(calls, 1);
  assert.match(safeErrorMessage(error, { chat: true }), /이전 질문 목록/);
});
for (const url of ["file:///local", "https://user:pass@example.invalid", "https://example.invalid/v1", "https://example.invalid/?key=fake", "https://example.invalid/#fragment"]) {
  test(`invalid backend configuration rejected: ${url}`, () => assert.throws(() => createApiClient(url, () => assert.fail("must not fetch"))));
}
for (const path of ["https://example.invalid/api/chat", "/health", "/api/chat?key=fake", "/api/chat#fragment"]) {
  test(`unsupported request path rejected before fetch: ${path}`, async () => {
    const request = createApiClient(base, () => assert.fail("must not fetch"));
    const error = await getError(() => request(path));
    assert.equal(error.code, "invalid_api_configuration");
  });
}
test("unknown timeout category cannot start a request", async () => {
  const request = createApiClient(base, () => assert.fail("must not fetch"));
  const error = await getError(() => request("/api/data", { kind: "unbounded" }));
  assert.equal(error.code, "invalid_api_configuration");
});

const results = [];
for (const { name, run } of cases) {
  try {
    await run();
    results.push({ name, passed: true });
  } catch (error) {
    results.push({ name, passed: false, error: String(error?.message || "assertion failed") });
  }
}
export const report = {
  scope: "pure frontend helpers and fake HTTP; no backend, Firebase, or AI requests",
  total: results.length,
  passed: results.filter((result) => result.passed).length,
  failed: results.filter((result) => !result.passed).length,
  results,
};
console.log(JSON.stringify({ total: report.total, passed: report.passed, failed: report.failed, failures: results.filter((result) => !result.passed) }));
assert.equal(report.failed, 0, "Frontend helper or fake HTTP regressions failed.");
