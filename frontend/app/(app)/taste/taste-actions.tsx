"use client";

import { useState, useTransition } from "react";
import { Copy, Check, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { buildEmbeddingAction, recomputeMatchesAction } from "@/lib/actions/taste-actions";
import { toast } from "@/components/ui/toast";

interface TasteActionsProps {
  hasData: boolean;
  publicTasteUrl?: string;
}

export function TasteActions({ hasData, publicTasteUrl }: TasteActionsProps) {
  const [copied, setCopied] = useState(false);
  const [isRecomputing, startRecompute] = useTransition();
  const [result, setResult] = useState<{ success?: boolean; error?: string } | null>(null);

  const handleCopy = async () => {
    const url = publicTasteUrl || window.location.href;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    toast.success("Profile link copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRecompute = async () => {
    if (!hasData) return;

    setResult(null);
    startRecompute(async () => {
      try {
        await buildEmbeddingAction();
        await recomputeMatchesAction();
        setResult({ success: true });
        toast.success("Taste profile refreshed");
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to recompute";
        setResult({ error: errorMsg });
        toast.error(errorMsg);
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