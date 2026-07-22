import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Plug } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { ServiceConnectGrid } from "@/components/connections/service-connect-grid";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Connections · SyncUp",
};

export default async function ConnectionsPage() {
  let connections;
  try {
    const me = await getCurrentUser();
    connections = me.connections;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={Plug}
          title="Connections"
          description="Link the platforms where your taste lives. We pull your data in the background after you connect."
        />

        <ServiceConnectGrid initialConnections={connections} />

        <p className="text-xs text-[var(--color-text-tertiary)]">
          Disconnecting a service isn&apos;t available yet — it will land when the
          backend ships{" "}
          <code className="rounded bg-[var(--color-bg-page)] px-1 py-0.5">
            DELETE /api/me/connections/&#123;service&#125;
          </code>
          .
        </p>
      </div>
    </div>
  );
}
