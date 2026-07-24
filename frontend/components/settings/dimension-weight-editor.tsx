"use client";

import { useMemo, useState, useTransition } from "react";
import { Loader2 } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/ui/error-message";
import { toast } from "@/components/ui/toast";
import { updateDimensionsAction } from "@/lib/actions/settings-actions";
import type { DimensionWeights } from "@/lib/api/dimensions";
import type { ServiceMeta } from "@/lib/constants/services";

interface DimensionWeightEditorProps {
  services: ServiceMeta[];
  initialWeights: DimensionWeights;
}

const SLIDER_MAX = 10;
const SLIDER_STEP = 0.5;

// Default weight for a connected service with no saved weight yet.
const DEFAULT_WEIGHT = 5;

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function computePercentages(weights: DimensionWeights): Record<string, number> {
  const total = Object.values(weights).reduce((sum, v) => sum + v, 0);
  if (total <= 0) {
    return Object.fromEntries(Object.keys(weights).map(([k]) => [k, 0]));
  }
  return Object.fromEntries(
    Object.entries(weights).map(([k, v]) => [k, (v / total) * 100]),
  );
}

export function DimensionWeightEditor({
  services,
  initialWeights,
}: DimensionWeightEditorProps) {
  const [weights, setWeights] = useState<DimensionWeights>(() => {
    const base: DimensionWeights = {};
    for (const service of services) {
      const saved = initialWeights[service.id];
      base[service.id] = saved !== undefined ? saved : DEFAULT_WEIGHT;
    }
    return base;
  });
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const percentages = useMemo(() => computePercentages(weights), [weights]);

  function handleSlider(serviceId: string, value: number) {
    setWeights((prev) => ({ ...prev, [serviceId]: value }));
  }

  function handleSave() {
    setError(null);
    startTransition(async () => {
      const result = await updateDimensionsAction(weights);
      if ("error" in result && result.error) {
        setError(result.error);
        toast.error(result.error);
        return;
      }
      toast.success("Taste weights saved");
    });
  }

  if (services.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-8 text-center">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Connect a service first to start weighting your taste dimensions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {error && <ErrorMessage>{error}</ErrorMessage>}

      <div className="space-y-5">
        {services.map((service) => {
          const value = weights[service.id] ?? DEFAULT_WEIGHT;
          const pct = percentages[service.id] ?? 0;
          return (
            <div key={service.id} className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <AppIcon
                    brand={service.brand}
                    size="xs"
                    brandColor={`#${service.brand.hex}`}
                  />
                  <div>
                    <div className="text-sm font-medium text-[var(--color-text-primary)]">
                      {service.name}
                    </div>
                    <div className="text-xs text-[var(--color-text-tertiary)]">
                      {formatPercent(pct)} of combined taste
                    </div>
                  </div>
                </div>
                <span className="w-10 text-right text-sm tabular-nums text-[var(--color-text-secondary)]">
                  {value.toFixed(1)}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={SLIDER_MAX}
                step={SLIDER_STEP}
                value={value}
                onChange={(e) => handleSlider(service.id, Number(e.target.value))}
                aria-label={`${service.name} weight`}
                className="h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--color-border)] accent-[var(--color-accent)]"
              />
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-[var(--color-border-subtle)] pt-5">
        <p className="text-xs text-[var(--color-text-tertiary)]">
          Weights are normalized to 100% when saved — only relative proportions
          matter.
        </p>
        <Button type="button" onClick={handleSave} disabled={pending} className="relative shrink-0">
          <span className={pending ? "invisible" : undefined}>Save weights</span>
          {pending && <Loader2 className="absolute h-4 w-4 animate-spin" />}
        </Button>
      </div>
    </div>
  );
}
