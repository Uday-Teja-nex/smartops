import { ApiError, describeApiDetail, describeLoginError } from "./api";
import { expect, it } from "vitest";

it("explains nested validation errors without including submitted values", () => {
  expect(describeApiDetail([{ loc: ["body", "detectionConfig", "zones", 0], msg: "Polygon edges must not cross", input: "private value" }]))
    .toBe("detectionConfig.zones.0: Polygon edges must not cross");
  expect(describeApiDetail("Source not found")).toBe("Source not found");
});

it("distinguishes throttling and temporary sign-in failure from network failures", () => {
  expect(describeLoginError(new ApiError("private backend detail", 401))).toBe("Invalid email or password.");
  expect(describeLoginError(new ApiError("private backend detail", 429))).toContain("Wait a minute");
  expect(describeLoginError(new ApiError("private backend detail", 503))).toContain("temporarily unavailable");
  expect(describeLoginError(new TypeError("Failed to fetch"))).toContain("Could not reach");
  expect(describeLoginError(new ApiError("private backend detail", 500))).not.toContain("private");
});
