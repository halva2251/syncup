"use client";

import { usePathname } from "next/navigation";
import { Check } from "lucide-react";

const steps = [
  { id: "profile", label: "Profile" },
  { id: "obsessions", label: "Obsessions" },
  { id: "services", label: "Services" },
  { id: "taste", label: "Taste" },
  { id: "matchable", label: "Matching" },
];

export function OnboardingStepper() {
  const pathname = usePathname();
  const currentId = pathname.split("/").pop() ?? "profile";
  const currentIndex = steps.findIndex((s) => s.id === currentId);

  return (
    <nav aria-label="Onboarding progress" className="mb-8">
      <ol className="flex items-center justify-between">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <li key={step.id} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-2">
                <div
                  className={[
                    "flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors",
                    isCompleted
                      ? "border-[var(--color-success)] bg-[var(--color-success)] text-white"
                      : isCurrent
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                        : "border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-tertiary)]",
                  ].join(" ")}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  ) : (
                    index + 1
                  )}
                </div>
                <span
                  className={[
                    "hidden text-xs font-medium sm:block",
                    isCompleted || isCurrent
                      ? "text-[var(--color-text-primary)]"
                      : "text-[var(--color-text-tertiary)]",
                  ].join(" ")}
                >
                  {step.label}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={[
                    "mx-2 h-0.5 flex-1 rounded-full",
                    index < currentIndex
                      ? "bg-[var(--color-success)]"
                      : "bg-[var(--color-border)]",
                  ].join(" ")}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
