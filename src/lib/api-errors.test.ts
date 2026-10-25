import { describeApiDetail } from "./api";
import { expect, it } from "vitest";

it("explains nested validation errors without including submitted values", () => {
  expect(describeApiDetail([{ loc: ["body", "detectionConfig", "zones", 0], msg: "Polygon edges must not cross", input: "private value" }]))
    .toBe("detectionConfig.zones.0: Polygon edges must not cross");
  expect(describeApiDetail("Source not found")).toBe("Source not found");
});
