"use client";

import {
  useEffect,
  useState,
  useTransition,
  useActionState,
} from "react";
import { AppIcon } from "@/components/ui/app-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { SERVICES } from "@/lib/constants/services";
import { SYNC_POLL_INTERVAL_MS } from "@/lib/utils/polling";
import { cn } from "@/lib/utils/cn";
import {
  connectSteamAction,
  connectLastfmAction,
  importCsvAction,
  triggerSyncAction,
  refreshConnections,
} from "@/lib/actions/connection-actions";
import {
  Loader2,
  RefreshCw,
  SendHorizontal,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { ServiceConnection } from "@/types/api";
import type { ServiceMeta } from "@/lib/constants/services";

interface ServiceConnectGridProps {
  initialConnections: ServiceConnection[];
  /** Optional notification that a connect/sync/import cycle started for a service. */
  onActivity?: (serviceId: string) => void;
  className?: string;
}

function formatStatus(status: string) {
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

function statusDotClass(status: string) {
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

export function ServiceConnectGrid({
  initialConnections,
  onActivity,
  className,
}: ServiceConnectGridProps) {
  const [connections, setConnections] = useState(initialConnections);
  const [activeServices, setActiveServices] = useState<Set<string>>(() => {
    return new Set(
      initialConnections
        .filter(
          (c) => c.sync_status === "pending" || c.sync_status === "syncing",
        )
        .map((c) => c.service),
    );
  });

  const activeServicesKey = Array.from(activeServices).sort().join(",");

  useEffect(() => {
    if (activeServices.size === 0) return;

    const interval = setInterval(async () => {
      try {
        const fresh = await refreshConnections();
        setConnections(fresh);
        setActiveServices((prev) => {
          const next = new Set<string>();
          for (const id of prev) {
            const conn = fresh.find((c) => c.service === id);
            if (
              conn &&
              (conn.sync_status === "pending" || conn.sync_status === "syncing")
            ) {
              next.add(id);
            }
          }
          return next;
        });
      } catch {
        // Stop polling on error to avoid spamming
        setActiveServices(new Set());
      }
    }, SYNC_POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [activeServicesKey, activeServices.size]);

  function markActive(service: string) {
    onActivity?.(service);
    setActiveServices((prev) => new Set(prev).add(service));
  }

  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-4 sm:grid-cols-2 grid-rows-[auto_auto]",
        className,
      )}
    >
      {SERVICES.map((service) => (
        <ServiceCard
          key={service.id}
          service={service}
          connection={connections.find((c) => c.service === service.id)}
          onActive={() => markActive(service.id)}
        />
      ))}
    </div>
  );
}

interface ServiceCardProps {
  service: ServiceMeta;
  connection?: ServiceConnection;
  onActive: () => void;
}

function ServiceCard({ service, connection, onActive }: ServiceCardProps) {
  const status = connection?.sync_status ?? "not_connected";
  const isBusy = status === "pending" || status === "syncing";
  const isConnected = status === "ok";

  return (
    <div className="relative grid row-span-2 grid-rows-subgrid h-full rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-page)] p-4">
      {/* grid-rows-subgrid is CSS Grid Level 2; supported in all modern browsers as of 2026. */}
      {isConnected && (
        <div className="absolute bottom-3 right-3 z-10 rotate-[-8deg] rounded-lg bg-[var(--color-success)] px-3 py-1.5 text-xs font-semibold text-white shadow-sm">
          Connected
        </div>
      )}
      <div className="row-start-1">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <AppIcon
              brand={service.brand}
              size="sm"
              brandColor={`#${service.brand.hex}`}
            />
            <div>
              <h3 className="font-semibold text-[var(--color-text-primary)]">
                {service.name}
              </h3>
              <p className="text-xs text-[var(--color-text-tertiary)]">
                {service.description}
              </p>
            </div>
          </div>
          {status !== "not_connected" && status !== "ok" && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-secondary)]">
              <span
                className={cn("h-2 w-2 rounded-full", statusDotClass(status))}
              />
              {formatStatus(status)}
            </span>
          )}
        </div>

        {connection?.sync_error && status === "error" && (
          <ErrorMessage className="mt-3 text-xs">
            {connection.sync_error}
          </ErrorMessage>
        )}
      </div>

      <div className="row-start-2 self-end">
        {service.type === "oauth" && service.oauthStartUrl && (
          <OAuthConnect
            service={service}
            isConnected={isConnected}
            isBusy={isBusy}
            onSync={onActive}
          />
        )}

        {service.type === "oauth_or_username" && service.oauthStartUrl && (
          <OAuthOrUsernameConnect
            service={service}
            isConnected={isConnected}
            isBusy={isBusy}
            onConnect={onActive}
            onConnected={onActive}
          />
        )}

        {service.type === "username" && (
          <UsernameConnect
            service={service}
            isConnected={isConnected}
            isBusy={isBusy}
            onConnected={onActive}
          />
        )}

        {service.type === "csv" && (
          <CsvImport
            service={service}
            isConnected={isConnected}
            isBusy={isBusy}
            onImported={onActive}
          />
        )}
      </div>
    </div>
  );
}

function OAuthConnect({
  service,
  isConnected,
  isBusy,
  onSync,
}: {
  service: ServiceMeta;
  isConnected: boolean;
  isBusy: boolean;
  onSync: () => void;
}) {
  const [isPending, startTransition] = useTransition();

  async function handleSync() {
    startTransition(async () => {
      const result = await triggerSyncAction(service.id);
      if (!("error" in result)) {
        onSync();
      }
    });
  }

  if (isConnected) {
    return (
      <button
        type="button"
        onClick={handleSync}
        disabled={isBusy || isPending}
        className="inline-flex h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-accent-light)] px-3.5 py-2 text-sm font-medium text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-accent-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:opacity-50"
      >
        {(isBusy || isPending) && <Loader2 className="h-4 w-4 animate-spin" />}
        <RefreshCw className="h-4 w-4" />
        Sync
      </button>
    );
  }

  return (
    <a
      href={service.oauthStartUrl}
      className="inline-flex h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-accent-light)] px-3.5 py-2 text-sm font-medium text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-accent-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:opacity-50"
      onClick={() => onSync()}
    >
      {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
      Connect
    </a>
  );
}

function OAuthOrUsernameConnect({
  service,
  isConnected,
  isBusy,
  onConnect,
  onConnected,
}: {
  service: ServiceMeta;
  isConnected: boolean;
  isBusy: boolean;
  onConnect: () => void;
  onConnected: () => void;
}) {
  const [showManual, setShowManual] = useState(false);

  if (isConnected) {
    return (
      <OAuthConnect
        service={service}
        isConnected={isConnected}
        isBusy={isBusy}
        onSync={onConnect}
      />
    );
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setShowManual((prev) => !prev)}
        className="inline-flex items-center gap-1 text-xs font-medium text-[var(--color-text-secondary)] underline-offset-2 hover:text-[var(--color-text-primary)] hover:underline"
      >
        manual entry
        {showManual ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>

      {showManual ? (
        <UsernameConnect
          service={service}
          isConnected={false}
          isBusy={isBusy}
          onConnected={onConnected}
        />
      ) : (
        <a
          href={service.oauthStartUrl}
          onClick={() => onConnect()}
          className="inline-flex h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-accent-light)] px-3.5 py-2 text-sm font-medium text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-accent-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:opacity-50"
        >
          {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
          Connect
        </a>
      )}
    </div>
  );
}

function UsernameConnect({
  service,
  isConnected,
  isBusy,
  onConnected,
}: {
  service: ServiceMeta;
  isConnected: boolean;
  isBusy: boolean;
  onConnected: () => void;
}) {
  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string } | null, formData: FormData) => {
      const action =
        service.id === "steam" ? connectSteamAction : connectLastfmAction;
      const result = await action(formData);
      if ("error" in result && result.error) {
        return { error: result.error };
      }
      onConnected();
      return null;
    },
    null,
  );

  const inputName = service.id === "steam" ? "steam_input" : "lastfm_username";
  const placeholder =
    service.id === "steam" ? "Steam ID or vanity URL" : "Last.fm username";

  return (
    <form action={formAction} className="space-y-2">
      {state?.error && (
        <ErrorMessage className="text-xs">{state.error}</ErrorMessage>
      )}
      <div className="flex gap-2">
        <Input
          name={inputName}
          placeholder={placeholder}
          required
          autoComplete="off"
          disabled={isBusy || pending}
          className="flex-1"
        />
        <Button
          type="submit"
          variant={isConnected ? "primary" : "accent-light"}
          disabled={isBusy || pending}
          className="h-[42px] w-[42px] shrink-0 items-center justify-center border-[var(--color-border)] p-0"
          aria-label="Connect"
        >
          {isBusy || pending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <SendHorizontal className="h-4 w-4" />
          )}
        </Button>
      </div>
    </form>
  );
}

function CsvImport({
  service,
  isConnected,
  isBusy,
  onImported,
}: {
  service: ServiceMeta;
  isConnected: boolean;
  isBusy: boolean;
  onImported: () => void;
}) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    startTransition(async () => {
      const result = await importCsvAction(service.id, formData);
      if ("error" in result && result.error) {
        setError(result.error);
      } else {
        onImported();
      }
    });
  }

  return (
    <div className="space-y-2">
      {error && <ErrorMessage className="text-xs">{error}</ErrorMessage>}
      <label
        className={cn(
          "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
          isConnected
            ? "border-transparent bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)]"
            : "border-[var(--color-border)] bg-[var(--color-accent-light)] text-[var(--color-text-primary)] hover:bg-[var(--color-accent-soft)]",
        )}
      >
        <span className="truncate">
          {isBusy || isPending ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Importing…
            </span>
          ) : fileName ? (
            fileName
          ) : (
            (service.csvLabel ?? "Choose CSV file")
          )}
        </span>
        <input
          type="file"
          name="file"
          accept=".csv,text/csv"
          onChange={handleChange}
          disabled={isBusy || isPending}
          className="sr-only"
        />
      </label>
    </div>
  );
}
