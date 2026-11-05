import { expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ServiceList } from "./SystemStatus";

it("lists every service with the operator impact of each failure", () => {
  const html = renderToStaticMarkup(
    <ServiceList status={{
      ok: false,
      checkedAt: "2026-11-06T00:00:00Z",
      components: [
        { id: "api", label: "API", ok: true, detail: "answering", impact: null },
        { id: "detector", label: "Object detection", ok: false, detail: "unreachable (ConnectError)",
          impact: "Live detection is paused: no new incidents until it returns." },
      ],
    }} />,
  );
  expect(html).toContain("Object detection");
  expect(html).toContain("Live detection is paused");
  expect(html.match(/aria-label="down"/g)).toHaveLength(1);
});

it("says plainly when the API itself cannot be reached", () => {
  expect(renderToStaticMarkup(<ServiceList status="error" />)).toContain("The API is unreachable");
});
