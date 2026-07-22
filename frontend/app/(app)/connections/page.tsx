import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { Plug } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { ServiceConnectGrid } from "@/components/connections/service-connect-grid";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Connections · SyncUp",
};

interface BackLink {
  href: string;
  label: string;
}

/** Pick a back-link from the Referer header, same-origin app routes only. */
function backLinkFromReferer(referer: string | null): BackLink {
  const KNOWN: Record<string, BackLink> = {
    "/home": { href: "/home", label: "Home" },
    "/settings": { href: "/settings", label: "Settings" },
  };
  if (referer) {
    try {
      const { pathname } = new URL(referer, "http://localhost");
      if (KNOWN[pathname]) return KNOWN[pathname];
    } catch {
      // malformed referer — fall through to default
    }
  }
  return KNOWN["/settings"];
}

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

  const referer = (await headers()).get("referer");
  const backLink = backLinkFromReferer(referer);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={Plug}
          title="Connections"
          description="Link the platforms where your taste lives. We pull your data in the background after you connect."
          backHref={backLink.href}
          backLabel={backLink.label}
        />

        <ServiceConnectGrid initialConnections={connections} allowDisconnect />
      </div>
    </div>
  );
}
