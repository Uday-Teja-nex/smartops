import { redirect } from "next/navigation";

// Crowding and queue incidents are listed in Live Ops; real per-zone counts
// are in Overview and Reports.
export default function OccupancyPage() {
  redirect("/live-ops?category=Queue%20%26%20Crowd");
}
