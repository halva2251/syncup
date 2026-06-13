"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import { OnboardingActions } from "@/components/onboarding/onboarding-actions";

interface OnboardingStepProps {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children: ReactNode;
  backHref?: string;
  backLabel?: string;
  continueHref?: string;
  continueButton?: Omit<
    ButtonHTMLAttributes<HTMLButtonElement>,
    "className" | "children"
  > & {
    children?: ReactNode;
    loading?: boolean;
  };
  continueLabel?: ReactNode;
}

export function OnboardingStep({
  icon,
  title,
  description,
  children,
  backHref,
  backLabel,
  continueHref,
  continueButton,
  continueLabel,
}: OnboardingStepProps) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-8 flex items-start gap-4">
        <AppIcon icon={icon} size="md" gradient="brand" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {title}
          </h1>
          <p className="mt-1 text-[15px] text-[var(--color-text-secondary)]">
            {description}
          </p>
        </div>
      </div>

      {children}

      <OnboardingActions
        backHref={backHref}
        backLabel={backLabel}
        continueHref={continueHref}
        continueButton={continueButton}
        continueLabel={continueLabel}
      />
    </div>
  );
}
