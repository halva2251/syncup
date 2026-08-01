"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/button";
import { refreshMatchesAction } from "@/lib/actions/match-actions";
import { toast } from "@/components/ui/toast";

interface FeedActionsProps {
  /** When true, renders the "enable matching" CTA instead of the refresh button. */
  disabled?: boolean;
}

/**
 * Header actions for the feed. In its default state it offers a "Refresh"
 * button that triggers a server-side match recompute (rate-limited 1/hour on the
 * backend). When `disabled`, it renders a link to privacy settings instead.
 */
export function FeedActions({ disabled = false }: FeedActionsProps) {
  const router = useRouter();
  const [isRefreshing, startRefresh] = useTransition();
  const [justRefreshed, setJustRefreshed] = useState(false);

  const handleRefresh = () => {
    startRefresh(async () => {
      const result = await refreshMatchesAction();
      if ("success" in result) {
        setJustRefreshed(true);
        toast.success("Refreshing matches. Check back in a moment.");
        // Give the background job a beat, then pull fresh results.
        setTimeout(() => router.refresh(), 4000);
        setTimeout(() => setJustRefreshed(false), 60000);
      } else {
        toast.error(result.error);
      }
    });
  };

  if (disabled) {
    return (
      <ButtonLink href="/settings/privacy" className="mt-5">
        Enable matching
      </ButtonLink>
    );
  }

  return (
    <Button
      variant="secondary"
      size="md"
      onClick={handleRefresh}
      disabled={isRefreshing || justRefreshed}
      className="gap-2"
    >
      <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
      {justRefreshed ? "Refreshed" : "Refresh matches"}
    </Button>
  );
}
