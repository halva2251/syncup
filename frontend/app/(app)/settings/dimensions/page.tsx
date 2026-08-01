import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getDimensions } from "@/lib/api/dimensions";
import { SERVICES, SERVICE_BY_ID } from "@/lib/constants/services";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { DimensionWeightEditor } from "@/components/settings/dimension-weight-editor";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Taste Dimensions · Settings · SyncUp",
};

export default async function DimensionsSettingsPage() {
  let connections;
  let weights;

  try {
    const [me, savedWeights] = await Promise.all([
      getCurrentUser(),
      getDimensions(),
    ]);
    connections = me.connections;
    weights = savedWeights;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  // Only show sliders for services the user has connected; weights for
  // unconnected services are meaningless and the backend trims them anyway.
  const connectedServiceIds = new Set(
    connections.map((c) => c.service).filter((id) => SERVICE_BY_ID.has(id)),
  );
  const connectedServices = SERVICES.filter((s) => connectedServiceIds.has(s.id));

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={SlidersHorizontal}
          title="Taste Dimensions"
          description="Weight how much each connected service contributes to your combined taste vector."
        />

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
          <DimensionWeightEditor
            services={connectedServices}
            initialWeights={weights}
          />
        </section>
      </div>
    </div>
  );
}
