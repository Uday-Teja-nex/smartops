import { redirect } from "next/navigation";

// Safety incidents (blocked exits) are listed in Live Ops; the former
// dashboard counted hazard types the pipeline never produces.
export default function SafetyPage() {
  redirect("/live-ops?category=Safety");
}
