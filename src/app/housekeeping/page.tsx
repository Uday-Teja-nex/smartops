import { redirect } from "next/navigation";

export default function HousekeepingPage() {
  redirect("/live-ops?category=Housekeeping");
}
