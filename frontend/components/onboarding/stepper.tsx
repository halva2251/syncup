"use client";

import { usePathname } from "next/navigation";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const steps = [
  { id: "profile", label: "Languages" },
  { id: "services", label: "Services" },
  { id: "socials", label: "Socials" },
  { id: "obsessions", label: "Obsessions" },
  { id: "taste", label: "Taste" },
];

export function OnboardingStepper() {
  const pathname = usePathname();
  const currentId = pathname.split("/").pop() ?? "profile";
  const currentIndex = steps.findIndex((s) => s.id === currentId);

  return (
    <nav aria-label="Onboarding progress" className="mb-8 w-full">
      <ol className="flex w-full">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <li
              key={step.id}
              className="flex flex-1 flex-col items-center"
              aria-current={isCurrent ? "step" : undefined}
            >
              <div className="relative flex h-8 w-full items-center justify-center">
                <div
                  className={cn(
                    "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors",
                    isCompleted
                      ? "border-[var(--color-accent-light)] bg-[var(--color-accent-light)] text-[var(--color-accent)]"
                      : isCurrent
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                        : "border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-tertiary)]",
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  ) : (
                    index + 1
                  )}
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={cn(
                      "absolute left-1/2 top-1/2 h-0.5 w-full -translate-y-1/2",
                      index < currentIndex
                        ? "bg-[var(--color-accent-light)]"
                        : "bg-[var(--color-border)]",
                    )}
                  />
                )}
              </div>
              <span
                className={cn(
                  "mt-2 hidden text-center text-xs font-medium sm:block",
                  isCompleted || isCurrent
                    ? "text-[var(--color-text-primary)]"
                    : "text-[var(--color-text-tertiary)]",
                )}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
