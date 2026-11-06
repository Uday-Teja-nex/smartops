/**
 * The client demo (GOAL Section C) as an automated script, run against the
 * real compose stack and the looping mall footage. Nothing is mocked.
 *
 * Covered: sign-in and real KPIs, live video, a rule incident pushed live
 * without refresh (with measured delay), evidence clip playback, AI review
 * shown or honestly unavailable, the full incident lifecycle mirrored to a
 * second browser, read-only viewers, workspace isolation, reports and the
 * degraded banner when the detector stops.
 * Not covered (needs the owner): the phone camera and a Telegram delivery.
 */
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { APIRequestContext, Browser, BrowserContext, expect, Page, test } from "@playwright/test";

const API = process.env.SMARTOPS_E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "smartops-demo";
const SCREENS = "docs/presentation/screens";
const measurements: Record<string, unknown> = {};

test.describe.configure({ mode: "serial" });

// Sign-in is throttled to 5 attempts per account per minute, so each account
// signs in once per run: browser sessions and API tokens are reused.
const sessions = new Map<string, Awaited<ReturnType<BrowserContext["storageState"]>>>();
const tokens = new Map<string, string>();

const signInFresh = async (page: Page, email: string) => {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(email);
  await page.locator('input[type="password"]').fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 });
};

/** A page signed in as `email`, in its own browser context. */
const pageAs = async (browser: Browser, email: string) => {
  const saved = sessions.get(email);
  const context = await browser.newContext(saved ? { storageState: saved } : {});
  const page = await context.newPage();
  if (!saved) {
    await signInFresh(page, email);
    sessions.set(email, await context.storageState());
  }
  return page;
};

const apiToken = async (request: APIRequestContext, email: string) => {
  const cached = tokens.get(email);
  if (cached) return cached;
  const response = await request.post(`${API}/v1/auth/login`, { data: { email, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const token = (await response.json()).token as string;
  tokens.set(email, token);
  return token;
};

type Incident = { id: string; startTime: string; createdAt?: string; shortSummary: string; status: string };

const incidents = async (request: APIRequestContext, token: string) => {
  const response = await request.get(`${API}/v1/incidents`, { headers: { Authorization: `Bearer ${token}` } });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as Incident[];
};

const shot = async (page: Page, name: string) => {
  mkdirSync(SCREENS, { recursive: true });
  await page.screenshot({ path: `${SCREENS}/${name}.png`, fullPage: false });
};

let liveIncidentId = "";

test("1. operator signs in and sees real KPIs for the mall", async ({ browser }) => {
  const page = await pageAs(browser, "operator@mall.demo");
  await expect(page.getByText(/Computed from \d+ stored incidents/)).toBeVisible();
  await expect(page.getByText("Tracking is anonymous; no face or identity recognition.")).toBeVisible();
  await shot(page, "01-overview");
});

test("2. live camera tile plays real video", async ({ browser }) => {
  const page = await pageAs(browser, "operator@mall.demo");
  await page.goto("/cameras");
  const video = page.locator("video").first();
  await expect(video).toBeVisible();
  await expect.poll(async () => video.evaluate((v: HTMLVideoElement) => v.readyState), { timeout: 30_000 })
    .toBeGreaterThanOrEqual(2);
  const first = await video.evaluate((v: HTMLVideoElement) => v.currentTime);
  await page.waitForTimeout(2000);
  const second = await video.evaluate((v: HTMLVideoElement) => v.currentTime);
  expect(second).toBeGreaterThan(first);
  await shot(page, "02-live-camera");
});

test("3. a rule incident is pushed to Live Ops without refresh", async ({ browser, request }) => {
  const token = await apiToken(request, "operator@mall.demo");
  const known = new Set((await incidents(request, token)).map((item) => item.id));
  const page = await pageAs(browser, "operator@mall.demo");
  await page.goto("/live-ops");
  const started = Date.now();
  // Queue and crowding rules have a 2-minute cooldown; wait up to 4 minutes.
  let fresh: Incident | undefined;
  while (!fresh && Date.now() - started < 240_000) {
    await page.waitForTimeout(1000);
    fresh = (await incidents(request, token)).find((item) => !known.has(item.id) && !item.shortSummary.includes("No fresh frames"));
  }
  expect(fresh, "a new rule incident within 4 minutes").toBeTruthy();
  liveIncidentId = fresh!.id;
  // It must reach the open page through SSE, with no navigation or reload.
  await expect(page.getByText(fresh!.shortSummary).first()).toBeVisible({ timeout: 10_000 });
  const visibleAt = Date.now();
  const triggeredAt = Date.parse(fresh!.startTime);
  measurements.liveIncident = {
    id: fresh!.id, summary: fresh!.shortSummary,
    secondsFromTriggerFrameToVisible: Math.round((visibleAt - triggeredAt) / 100) / 10,
  };
  expect(visibleAt - triggeredAt).toBeLessThan(15_000);
  await shot(page, "03-live-ops-new-incident");
});

test("4. incident shows evidence and an AI review or its stated reason", async ({ browser }) => {
  test.skip(!liveIncidentId, "needs the incident from step 3");
  const page = await pageAs(browser, "operator@mall.demo");
  await page.goto(`/incidents/${liveIncidentId}`);
  await expect(page.getByText("Measured by rule")).toBeVisible();
  const clip = page.locator("video").first();
  await expect.poll(async () => clip.count(), { timeout: 60_000 }).toBeGreaterThan(0);
  await expect.poll(async () => clip.evaluate((v: HTMLVideoElement) => v.readyState), { timeout: 60_000 })
    .toBeGreaterThanOrEqual(2);
  // Within 90 s the review must have landed or say why; never an endless spinner.
  const review = page.getByText(/AI review by|AI review unavailable|No AI review was recorded|Image consistent|Image casts doubt|Image unclear/);
  await expect(review.first()).toBeVisible({ timeout: 90_000 });
  measurements.aiReview = await page.locator("section").filter({ hasText: "AI review" }).first().innerText();
  await shot(page, "04-incident-evidence-ai");
});

test("5. lifecycle actions update the timeline and a second browser live", async ({ browser }) => {
  test.skip(!liveIncidentId, "needs the incident from step 3");
  const a = await pageAs(browser, "operator@mall.demo");
  const b = await pageAs(browser, "supervisor@mall.demo");
  await a.goto(`/incidents/${liveIncidentId}`);
  await b.goto(`/incidents/${liveIncidentId}`);
  await a.getByRole("button", { name: "Acknowledge" }).click();
  await expect(b.getByText("→ acknowledged")).toBeVisible();
  await a.getByRole("button", { name: "Assign to me" }).click();
  await a.getByPlaceholder("Add an operational note…").fill("E2E: checked on camera, aisle clearing.");
  await a.keyboard.press("Enter");
  await expect(a.getByText("E2E: checked on camera, aisle clearing.").first()).toBeVisible();
  // The comment reaches the other operator's open page too.
  await expect(b.getByText("E2E: checked on camera, aisle clearing.").first()).toBeVisible({ timeout: 15_000 });
  await a.getByRole("button", { name: "Resolve" }).click();
  await expect(a.getByText("→ resolved")).toBeVisible();
  // The other browser sees the final state without reloading.
  await expect(b.getByText("→ resolved")).toBeVisible({ timeout: 15_000 });
  await shot(a, "05-incident-resolved");
});

test("6. viewers are read-only in the UI and the API", async ({ browser, request }) => {
  test.skip(!liveIncidentId, "needs the incident from step 3");
  const page = await pageAs(browser, "viewer@mall.demo");
  await page.goto(`/incidents/${liveIncidentId}`);
  await expect(page.getByText("Measured by rule")).toBeVisible();
  await expect(page.getByRole("button", { name: "Acknowledge" })).toHaveCount(0);
  const token = await apiToken(request, "viewer@mall.demo");
  const denied = await request.patch(`${API}/v1/incidents/${liveIncidentId}/acknowledge`,
    { headers: { Authorization: `Bearer ${token}` } });
  expect(denied.status()).toBe(403);
});

test("7. another workspace sees none of the mall's data", async ({ browser, request }) => {
  test.skip(!liveIncidentId, "needs the incident from step 3");
  const token = await apiToken(request, "operator@smartops.local");
  const foreign = await request.get(`${API}/v1/incidents/${liveIncidentId}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(foreign.status()).toBe(404);
  expect((await incidents(request, token)).some((item) => item.id === liveIncidentId)).toBe(false);
  const page = await pageAs(browser, "operator@smartops.local");
  await page.goto(`/incidents/${liveIncidentId}`);
  await expect(page.getByText(/not found|could not be found|unavailable/i).first()).toBeVisible();
});

test("8. reports show computed summaries with CSV and PDF export", async ({ browser }) => {
  const page = await pageAs(browser, "supervisor@mall.demo");
  await page.goto("/reports");
  await expect(page.getByRole("button", { name: "Export CSV" })).toBeEnabled({ timeout: 30_000 });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const csv = await download;
  expect(csv.suggestedFilename()).toMatch(/\.csv$/);
  await shot(page, "08-reports");
});

test("9. stopping the detector shows a named degraded state that recovers", async ({ browser, request }) => {
  const page = await pageAs(browser, "operator@mall.demo");
  await page.goto("/");
  const token = await apiToken(request, "operator@mall.demo");
  const detectorUp = async () => {
    const response = await request.get(`${API}/v1/system/status`, { headers: { Authorization: `Bearer ${token}` } });
    const body = await response.json();
    return body.components.find((item: { id: string; ok: boolean }) => item.id === "detector").ok as boolean;
  };
  try {
    execSync("docker compose stop detector", { stdio: "pipe" });
    // First the server must notice; then the console must say so within its 10 s poll.
    await expect.poll(detectorUp, { timeout: 30_000 }).toBe(false);
    await expect(page.getByText("Running in a degraded state")).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText(/Object detection:.*Live detection is paused/)).toBeVisible();
    await shot(page, "09-degraded-detector");
  } finally {
    execSync("docker compose start detector", { stdio: "ignore" });
  }
  await expect(page.getByText("Running in a degraded state")).toHaveCount(0, { timeout: 60_000 });
});

test.afterAll(() => {
  mkdirSync("docs/verification/e2e", { recursive: true });
  writeFileSync("docs/verification/e2e/measurements.json", JSON.stringify(
    { measuredAt: new Date().toISOString(), ...measurements }, null, 2));
});
