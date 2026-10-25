"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@/app/auth";
import { useSmartOps } from "@/app/providers";
import { SectionHeader } from "@/components/SectionHeader";
import { ZoneEditor } from "@/components/ZoneEditor";

export default function ZoneEditorPage() {
  const { id } = useParams<{ id: string }>();
  const { sources } = useSmartOps();
  const { hasRole } = useAuth();
  const source = sources.find((item) => item.id === id);
  if (!hasRole("supervisor")) return <p>Zone editing requires a supervisor or administrator.</p>;
  if (!source) return <p>Source not found.</p>;
  return <div className="space-y-6"><SectionHeader title={`Zones · ${source.name}`} subtitle="Draw boundaries on a frozen camera frame and configure measured rules." /><ZoneEditor key={source.id} source={source} /></div>;
}
