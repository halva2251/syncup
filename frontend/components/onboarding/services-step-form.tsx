"use client";

import { useActionState, useEffect, useState, useTransition } from "react";
import { AppIcon } from "@/components/ui/app-icon";
import { Button, ButtonLink } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { SERVICES, SERVICE_BY_ID } from "@/lib/constants/services";
import {
  connectSteamAction,
  connectLastfmAction,
  importCsvAction,
  triggerSyncAction,
  refreshConnections,
} from "@/lib/actions/connection-actions";
import { Loader2, Link2, RefreshCw } from "lucide-react";
import type { ServiceConnection } from "@/types/api";

interface ServicesStepFormProps {
  initialConnections: ServiceConnection[];
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

export function ServicesStepForm({
  initialConnections,
}: ServicesStepFormProps) {
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
    }, 2000);

    return () => clearInterval(interval);
  }, [activeServices]);

  function markActive(service: string) {
    setActiveServices((prev) => new Set(prev).add(service));
  }

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-8 flex items-start gap-4">
        <AppIcon icon={Link2} size="md" gradient="brand" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Connect your services
          </h1>
          <p className="mt-1 text-[15px] text-[var(--color-text-secondary)]">
            Link the platforms where your taste actually lives. You can skip any
            service and add manual obsessions next.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SERVICES.map((service) => (
          <ServiceCard
            key={service.id}
            service={service}
            connection={connections.find((c) => c.service === service.id)}
            onActive={() => markActive(service.id)}
          />
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between gap-3">
        <ButtonLink
          href="/onboarding/profile"
          variant="secondary"
          size="lg"
          className="bg-[var(--color-bg-card)]"
        >
          Back
        </ButtonLink>
        <ButtonLink href="/onboarding/obsessions" size="lg">
          Continue
        </ButtonLink>
      </div>
    </div>
  );
}

interface ServiceCardProps {
  service: {
    id: string;
    name: string;
    type: "username" | "oauth" | "csv";
    brand: { title: string; path: string };
    description: string;
    oauthStartUrl?: string;
    csvLabel?: string;
  };
  connection?: ServiceConnection;
  onActive: () => void;
}

function ServiceCard({ service, connection, onActive }: ServiceCardProps) {
  const status = connection?.sync_status ?? "not_connected";
  const isBusy = status === "pending" || status === "syncing";
  const isConnected = status === "ok";

  return (
    <div className="flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-page)] p-4">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <AppIcon brand={service.brand} size="sm" gradient="brand" />
          <div>
            <h3 className="font-semibold text-[var(--color-text-primary)]">
              {service.name}
            </h3>
            <p className="text-xs text-[var(--color-text-tertiary)]">
              {service.description}
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-secondary)]">
          <span
            className={["h-2 w-2 rounded-full", statusDotClass(status)].join(
              " ",
            )}
          />
          {formatStatus(status)}
        </span>
      </div>

      {connection?.sync_error && status === "error" && (
        <ErrorMessage className="mb-3 text-xs">
          {connection.sync_error}
        </ErrorMessage>
      )}

      <div className="mt-auto">
        {service.type === "oauth" && service.oauthStartUrl && (
          <OAuthConnect
            service={service}
            isConnected={isConnected}
            isBusy={isBusy}
            onSync={onActive}
          />
        )}

        {service.type === "username" && (
          <UsernameConnect
            service={service}
            isBusy={isBusy}
            onConnected={onActive}
          />
        )}

        {service.type === "csv" && (
          <CsvImport service={service} isBusy={isBusy} onImported={onActive} />
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
  service: ServiceCardProps["service"];
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
      <Button
        variant="secondary"
        size="sm"
        className="w-full"
        onClick={handleSync}
        disabled={isBusy || isPending}
      >
        {(isBusy || isPending) && <Loader2 className="h-4 w-4 animate-spin" />}
        <RefreshCw className="h-4 w-4" />
        Sync
      </Button>
    );
  }

  return (
    <a
      href={service.oauthStartUrl}
      className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-transparent bg-[var(--color-accent)] px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:opacity-50"
      onClick={() => onSync()}
    >
      {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
      Connect {service.name}
    </a>
  );
}

function UsernameConnect({
  service,
  isBusy,
  onConnected,
}: {
  service: ServiceCardProps["service"];
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
        <Button type="submit" disabled={isBusy || pending}>
          {(isBusy || pending) && <Loader2 className="h-4 w-4 animate-spin" />}
          Connect
        </Button>
      </div>
    </form>
  );
}

function CsvImport({
  service,
  isBusy,
  onImported,
}: {
  service: ServiceCardProps["service"];
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
      <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-2 text-sm text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-bg-page)]">
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
