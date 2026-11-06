import { expect, it } from "vitest";
import { parseFloors } from "./WorkspaceCreator";

it("parses one floor per line with comma-separated zones", () => {
  expect(parseFloors("G: Main entrance, Checkout queue\n\nL1: Food court\nL2")).toEqual([
    { level: "G", name: "Level G", zones: ["Main entrance", "Checkout queue"] },
    { level: "L1", name: "Level L1", zones: ["Food court"] },
    { level: "L2", name: "Level L2", zones: [] },
  ]);
});
