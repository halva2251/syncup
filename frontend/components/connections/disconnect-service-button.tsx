"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Unplug, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/ui/error-message";
import { disconnectConnectionAction } from "@/lib/actions/connection-actions";

interface DisconnectServiceButtonProps {
  serviceId: string;
  serviceName: string;
  compact?: boolean;
  fullWidth?: boolean;
  onDisconnected?: () => void;
}

export function DisconnectServiceButton({
  serviceId,
  serviceName,
  compact = false,
  fullWidth = false,
  onDisconnected,
}: DisconnectServiceButtonProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleDisconnect() {
    setError(null);
    startTransition(async () => {
      const result = await disconnectConnectionAction(serviceId);
      if ("error" in result && result.error) {
        setError(result.error);
        return;
      }

      onDisconnected?.();
      router.refresh();
    });
  }

  return (
    <div className={`${fullWidth ? "w-full" : ""} ${compact ? "" : "space-y-2"}`}>
      <Button
        type="button"
        variant="secondary"
        size={compact ? "sm" : "md"}
        onClick={handleDisconnect}
        disabled={isPending}
        aria-busy={isPending}
        className={
          compact
            ? "border-[var(--color-danger)]/30 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
            : "h-[42px] w-full border-[var(--color-danger)]/30 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
        }
        aria-label={`Disconnect ${serviceName}`}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Unplug className="h-4 w-4" />
        )}
        Disconnect
      </Button>
      {error && <ErrorMessage className="text-xs">{error}</ErrorMessage>}
    </div>
  );
}
