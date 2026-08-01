import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Plug } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import { AppIcon } from "@/components/ui/app-icon";
import { ButtonLink } from "@/components/ui/button";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { cn } from "@/lib/utils/cn";
import type { ServiceConnection } from "@/types/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Connected Services · Settings · SyncUp",
};

function formatStatus(status: string): string {
  switch (status) {
    case "ok":
      return "Connected";
    case "pending":
      return "Pending";
    case "syncing":
      return "Syncing";
    case "error":
      return "Error";
    default:
      return "Not connected";
  }
}

function statusDotClass(status: string): string {
  switch (status) {
    case "ok":
      return "bg-[var(--color-success)]";
    case "pending":
    case "syncing":
      return "bg-[var(--color-warning)]";
    case "error":
      return "bg-[var(--color-danger)]";
    default:
      return "bg-[var(--color-text-tertiary)]";
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function ServicesSettingsPage() {
  let connections: ServiceConnection[] = [];
  try {
    const me = await getCurrentUser();
    connections = me.connections;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  const hasConnections = connections.length > 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={Plug}
          title="Connected Services"
          description="Sync status for the platforms feeding your taste profile."
        />

        {hasConnections ? (
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
            <ul className="divide-y divide-[var(--color-border-subtle)]">
              {connections.map((connection) => {
                const service = SERVICE_BY_ID.get(connection.service);
                const name = service?.name ?? connection.service;
                return (
                  <li
                    key={connection.service}
                    className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex items-center gap-3">
                      {service ? (
                        <AppIcon
                          brand={service.brand}
                          size="xs"
                          brandColor={`#${service.brand.hex}`}
                        />
                      ) : null}
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-[var(--color-text-primary)]">
                          {name}
                        </div>
                        <div className="truncate text-xs text-[var(--color-text-tertiary)]">
                          Last synced {formatTimestamp(connection.last_synced_at)}
                        </div>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1.5 self-start text-xs font-medium text-[var(--color-text-secondary)] sm:self-auto">
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full",
                          statusDotClass(connection.sync_status),
                        )}
                      />
                      {formatStatus(connection.sync_status)}
                    </span>
                  </li>
                );
              })}
            </ul>

            {connections.some((c) => c.sync_error) && (
              <div className="mt-4 space-y-2">
                {connections
                  .filter((c) => c.sync_error)
                  .map((c) => (
                    <p
                      key={c.service}
                      className="text-xs text-[var(--color-danger)]"
                    >
                      {SERVICE_BY_ID.get(c.service)?.name ?? c.service}:{" "}
                      {c.sync_error}
                    </p>
                  ))}
              </div>
            )}

            <div className="mt-5 flex justify-end border-t border-[var(--color-border-subtle)] pt-5">
              <ButtonLink href="/connections" variant="secondary" size="md">
                Manage connections
              </ButtonLink>
            </div>
          </section>
        ) : (
          <section className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-10 text-center">
            <Plug className="mx-auto h-10 w-10 text-[var(--color-text-tertiary)]" />
            <h2 className="mt-4 text-base font-medium text-[var(--color-text-primary)]">
              No services connected yet
            </h2>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-[var(--color-text-secondary)]">
              Connect a platform to start building the taste profile used for
              matches and recommendations.
            </p>
            <ButtonLink href="/connections" className="mt-5">
              Connect your first service
            </ButtonLink>
          </section>
        )}
      </div>
    </div>
  );
}
