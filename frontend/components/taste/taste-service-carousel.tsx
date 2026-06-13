"use client";

import { useEffect, useState, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import { TasteServiceSection } from "@/components/taste/taste-service-section";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import type { TasteResponse } from "@/types/api";

interface TasteServiceCarouselProps {
  serviceIds: string[];
  services: TasteResponse["services"];
}

export function TasteServiceCarousel({
  serviceIds,
  services,
}: TasteServiceCarouselProps) {
  const [index, setIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const next = useCallback(() => {
    setIndex((prev) => (prev + 1) % serviceIds.length);
  }, [serviceIds.length]);

  const previous = useCallback(() => {
    setIndex((prev) => (prev - 1 + serviceIds.length) % serviceIds.length);
  }, [serviceIds.length]);

  const goTo = useCallback(
    (i: number) => {
      setIndex(((i % serviceIds.length) + serviceIds.length) % serviceIds.length);
    },
    [serviceIds.length],
  );

  useEffect(() => {
    if (isHovered || isFocused || serviceIds.length <= 1) return;

    const timer = setInterval(next, 10000);
    return () => clearInterval(timer);
  }, [isHovered, isFocused, next, serviceIds.length]);

  if (serviceIds.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">
        From your connected services
      </h3>

      <div
        className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
      >
        <div
          className="flex gap-4 transition-transform duration-500 ease-in-out"
          style={{ transform: `translateX(calc(-${index} * (100% + 16px)))` }}
        >
          {serviceIds.map((serviceId) => (
            <div
              key={serviceId}
              className="w-full flex-shrink-0"
              aria-hidden={serviceIds[index] !== serviceId}
            >
              <TasteServiceSection
                serviceId={serviceId}
                data={services[serviceId]}
                bordered={false}
              />
            </div>
          ))}
        </div>
      </div>

      {serviceIds.length > 1 && (
        <div className="flex items-center justify-end gap-3">
            <div className="flex items-center gap-1.5">
              {serviceIds.map((serviceId, i) => {
                const service = SERVICE_BY_ID.get(serviceId);
                const isCurrent = i === index;
                return (
                  <button
                    key={serviceId}
                    type="button"
                    onClick={() => goTo(i)}
                    className="relative rounded-md p-1 transition-opacity hover:opacity-80"
                    aria-label={`Go to ${service?.name ?? serviceId}`}
                  >
                    {service ? (
                      <AppIcon
                        brand={service.brand}
                        size="xs"
                        brandColor={isCurrent ? `#${service.brand.hex}` : "var(--color-text-tertiary)"}
                        className={isCurrent ? "" : "opacity-40"}
                      />
                    ) : (
                      <span className="text-xs text-[var(--color-text-tertiary)]">
                        {serviceId}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={previous}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-page)]"
                aria-label="Previous service"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <button
                type="button"
                onClick={next}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-page)]"
                aria-label="Next service"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
        </div>
      )}
    </div>
  );
}
