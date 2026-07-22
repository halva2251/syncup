"use client";

import { useEffect, useState, useCallback, useId, useRef } from "react";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import { TasteServiceSection } from "@/components/taste/taste-service-section";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import type { TasteResponse } from "@/types/api";

interface TasteServiceCarouselProps {
  serviceIds: string[];
  services: TasteResponse["services"];
  connectedServiceIds?: string[];
  editable?: boolean;
  viewerIsOwner?: boolean;
}

const AUTO_ADVANCE_MS = 10000;

export function TasteServiceCarousel({
  serviceIds,
  services,
  connectedServiceIds,
  editable = false,
  viewerIsOwner = true,
}: TasteServiceCarouselProps) {
  const [index, setIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const labelId = useId();
  const progressLayerRef = useRef<HTMLSpanElement>(null);
  const progressIndexRef = useRef(0);
  const progressElapsedRef = useRef(0);

  const safeIndex = Math.max(0, Math.min(index, serviceIds.length - 1));
  const autoAdvancePaused =
    isHovered || isFocused || isPaused || prefersReducedMotion;

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
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setPrefersReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const layer = progressLayerRef.current;
    if (!layer) return;

    if (progressIndexRef.current !== safeIndex) {
      progressIndexRef.current = safeIndex;
      progressElapsedRef.current = 0;
    }

    const setClip = (elapsed: number) => {
      const progress = Math.min(100, (elapsed / AUTO_ADVANCE_MS) * 100);
      layer.style.clipPath = `inset(${progress}% 0 0 0)`;
    };
    setClip(progressElapsedRef.current);

    if (autoAdvancePaused || serviceIds.length <= 1) return;

    const startedAt = performance.now() - progressElapsedRef.current;
    let frameId = 0;
    const animate = (now: number) => {
      progressElapsedRef.current = Math.min(AUTO_ADVANCE_MS, now - startedAt);
      setClip(progressElapsedRef.current);
      if (progressElapsedRef.current < AUTO_ADVANCE_MS) {
        frameId = requestAnimationFrame(animate);
      }
    };
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [autoAdvancePaused, safeIndex, serviceIds.length]);

  useEffect(() => {
    if (
      autoAdvancePaused ||
      serviceIds.length <= 1
    ) {
      return;
    }

    const timer = setInterval(next, AUTO_ADVANCE_MS);
    return () => clearInterval(timer);
  }, [autoAdvancePaused, next, serviceIds.length]);

  if (serviceIds.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3
        id={labelId}
        className="text-sm font-medium text-[var(--color-text-secondary)]"
      >
        From {viewerIsOwner ? "your" : "their"} connected services
      </h3>

      <div
        role="region"
        aria-roledescription="carousel"
        aria-labelledby={labelId}
        className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
      >
        <div
          className={
            prefersReducedMotion
              ? "flex gap-4"
              : "flex gap-4 transition-transform duration-500 ease-in-out"
          }
          style={{ transform: `translateX(calc(-${safeIndex} * (100% + 16px)))` }}
        >
          {serviceIds.map((serviceId) => {
            const hidden = serviceIds[safeIndex] !== serviceId;
            return (
              <div
                key={serviceId}
                className="w-full flex-shrink-0"
                aria-hidden={hidden}
                inert={hidden ? true : undefined}
              >
                <TasteServiceSection
                  serviceId={serviceId}
                  data={services[serviceId]}
                  bordered={false}
                  canDisconnect={connectedServiceIds?.includes(serviceId) ?? false}
                  canEditItems={editable}
                />
              </div>
            );
          })}
        </div>
      </div>

      {serviceIds.length > 1 && (
        <div className="flex items-center justify-end gap-3">
            <div className="flex items-center gap-1.5">
              {serviceIds.map((serviceId, i) => {
                const service = SERVICE_BY_ID.get(serviceId);
                const isCurrent = i === safeIndex;
                return (
                  <button
                    key={serviceId}
                    type="button"
                    onClick={() => goTo(i)}
                    className="relative rounded-md p-1 transition-opacity hover:opacity-80"
                    aria-label={`Go to ${service?.name ?? serviceId}`}
                  >
                  {service ? (
                      <span className="relative block h-8 w-8">
                        <AppIcon
                          brand={service.brand}
                          size="xs"
                          brandColor="var(--color-text-tertiary)"
                          className="opacity-40"
                        />
                        {isCurrent ? (
                          <span
                            ref={progressLayerRef}
                            className="absolute inset-0"
                          >
                            <AppIcon
                              brand={service.brand}
                              size="xs"
                              brandColor={`#${service.brand.hex}`}
                            />
                          </span>
                        ) : null}
                      </span>
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
                onClick={() => setIsPaused((value) => !value)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-page)]"
                aria-label={isPaused ? "Play carousel" : "Pause carousel"}
                aria-pressed={isPaused}
              >
                {isPaused ? (
                  <Play className="h-4 w-4" />
                ) : (
                  <Pause className="h-4 w-4" />
                )}
              </button>

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
