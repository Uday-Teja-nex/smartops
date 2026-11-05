import { expect, it } from "vitest";
import { humanize } from "./utils";

it("turns enum values into readable labels without mangling names", () => {
  expect(humanize("false_positive")).toBe("False positive");
  expect(humanize("queue_build_up")).toBe("Queue build up");
  expect(humanize("in_progress")).toBe("In progress");
  expect(humanize("low")).toBe("Low");
  expect(humanize("Queue & Crowd")).toBe("Queue & Crowd");
  expect(humanize("All")).toBe("All");
});
