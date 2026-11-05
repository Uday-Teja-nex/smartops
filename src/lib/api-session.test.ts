import { afterEach, beforeEach, expect, it, vi } from "vitest";

const store = new Map<string, string>();
const events: string[] = [];

beforeEach(() => {
  store.clear();
  events.length = 0;
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
    },
    dispatchEvent: (event: Event) => events.push(event.type),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

it("refreshes once for concurrent 401s and retries with the new token", async () => {
  store.set("smartops.token", "stale");
  const seen: { path: string; auth: string | null; credentials?: RequestCredentials }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    const path = new URL(url).pathname;
    const auth = new Headers(init.headers).get("Authorization");
    seen.push({ path, auth, credentials: init.credentials });
    if (path === "/v1/auth/refresh") return json(200, { token: "fresh", expiresInSeconds: 900, user: {} });
    return auth === "Bearer fresh" ? json(200, []) : json(401, { detail: "Token expired" });
  }));
  const api = await import("./api");
  await Promise.all([api.fetchSources(), api.fetchUsers()]);
  expect(seen.filter((call) => call.path === "/v1/auth/refresh")).toHaveLength(1);
  expect(seen.find((call) => call.path === "/v1/auth/refresh")?.credentials).toBe("include");
  expect(store.get("smartops.token")).toBe("fresh");
  expect(seen.filter((call) => call.auth === "Bearer fresh")).toHaveLength(2);
});

it("signs out when the refresh cookie is rejected", async () => {
  store.set("smartops.token", "stale");
  vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "Session expired" })));
  const api = await import("./api");
  await expect(api.fetchSources()).rejects.toMatchObject({ status: 401 });
  expect(store.has("smartops.token")).toBe(false);
  expect(events).toContain(api.SIGNED_OUT_EVENT);
});

it("keeps the session when the API is unreachable during refresh", async () => {
  store.set("smartops.token", "stale");
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (new URL(url).pathname === "/v1/auth/refresh") throw new TypeError("Failed to fetch");
    return json(401, { detail: "Token expired" });
  }));
  const api = await import("./api");
  await expect(api.fetchSources()).rejects.toThrow("Failed to fetch");
  expect(store.get("smartops.token")).toBe("stale");
  expect(events).toHaveLength(0);
});
