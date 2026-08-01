"use client";

import { useState, useTransition } from "react";
import { Check, Copy, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { buildEmbeddingAction } from "@/lib/actions/taste-actions";

interface TasteActionsProps {
  hasData: boolean;
  publicTasteUrl?: string;
}

/** Profile actions for sharing and rebuilding the signed-in user's taste data. */
export function TasteActions({ hasData, publicTasteUrl }: TasteActionsProps) {
  const [copied, setCopied] = useState(false);
  const [isRecomputing, startRecompute] = useTransition();

  const handleCopy = async () => {
    const url = publicTasteUrl || window.location.href;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    toast.success("Profile link copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRecompute = () => {
    if (!hasData) return;

    startRecompute(async () => {
      try {
        await buildEmbeddingAction();
        toast.success("Taste profile refreshed");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to recompute");
      }
    });
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="secondary"
        size="md"
        onClick={handleCopy}
        disabled={!hasData}
        className="gap-2"
      >
        {copied ? (
          <>
            <Check className="h-4 w-4" />
            <span className="hidden sm:inline">Copied</span>
          </>
        ) : (
          <>
            <Copy className="h-4 w-4" />
            <span className="hidden sm:inline">Copy link</span>
          </>
        )}
      </Button>

      <Button
        variant="secondary"
        size="md"
        onClick={handleRecompute}
        disabled={!hasData || isRecomputing}
        className="gap-2"
      >
        <RefreshCw className={`h-4 w-4 ${isRecomputing ? "animate-spin" : ""}`} />
        <span className="hidden sm:inline">
          {isRecomputing ? "Recomputing..." : "Refresh"}
        </span>
      </Button>
    </div>
  );
}
