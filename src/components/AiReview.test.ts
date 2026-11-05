import { expect, it } from "vitest";
import { otherNotes, reviewStateOf } from "./AiReview";
import { EventRecord } from "@/lib/types";

const base = {
  id: "inc-1",
  type: "crowding",
  shortSummary: "3 people in Front aisle for 5s (crowding limit exceeded)",
  startTime: "2026-11-06T10:00:00Z",
  modelProvider: "rule-engine",
  modelVersion: "zone-rules-v1",
  detailedNarrative: [] as string[],
  recommendedActions: [] as string[],
  reviewNotes: [] as string[],
} as unknown as EventRecord;
const created = Date.parse("2026-11-06T10:00:00Z");

it("reads a completed review with model, verdict, scene and limits", () => {
  const event = {
    ...base,
    detailedNarrative: ["Three shoppers in an aisle.", "Shelves on both sides."],
    recommendedActions: ["Check the aisle camera."],
    reviewNotes: ["Evidence clip shortened", "AI review by qwen2.5vl:3b (2.1 s): image looks consistent with the measured event. Rule decision unchanged.", "Cannot count people outside the frame."],
    detectionSummary: { aiReview: { model: "qwen2.5vl:3b", verdict: "consistent", latencyMs: 2100 } },
  } as EventRecord;
  const state = reviewStateOf(event, created + 5000);
  expect(state).toMatchObject({ kind: "reviewed", model: "qwen2.5vl:3b", verdict: "consistent", latencyMs: 2100,
    scene: "Three shoppers in an aisle.", observations: ["Shelves on both sides."],
    limitations: ["Cannot count people outside the frame."] });
  expect(otherNotes(event)).toEqual(["Evidence clip shortened"]);
});

it("states the failure reason instead of inventing content", () => {
  const event = { ...base, reviewNotes: ["AI review unavailable: model provider daily request limit reached."] } as EventRecord;
  expect(reviewStateOf(event, created)).toEqual({ kind: "unavailable", reason: "model provider daily request limit reached" });
});

it("shows pending only briefly, never as an endless spinner", () => {
  expect(reviewStateOf(base, created + 10_000).kind).toBe("pending");
  expect(reviewStateOf(base, created + 120_000).kind).toBe("none");
});

it("keeps a queued review visible as queued, however long the backlog", () => {
  const event = { ...base, reviewNotes: ["AI review queued; measured rule incident remains active."] } as EventRecord;
  expect(reviewStateOf(event, created + 600_000).kind).toBe("queued");
});
