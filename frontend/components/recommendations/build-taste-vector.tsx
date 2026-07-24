"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { buildEmbeddingAction } from "@/lib/actions/taste-actions";

/** Builds the combined taste vector required by the recommendations endpoint. */
export function BuildTasteVector() {
  const router = useRouter();
  const [isBuilding, startTransition] = useTransition();

  const handleBuild = () => {
    startTransition(async () => {
      try {
        await buildEmbeddingAction();
        toast.success("Your taste vector is being built. Check back in a moment.");
        setTimeout(() => router.refresh(), 4000);
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Could not build your taste vector.",
        );
      }
    });
  };

  return (
    <Button onClick={handleBuild} disabled={isBuilding} className="mt-5 gap-2">
      <Sparkles className={isBuilding ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
      {isBuilding ? "Building…" : "Build taste vector"}
    </Button>
  );
}
