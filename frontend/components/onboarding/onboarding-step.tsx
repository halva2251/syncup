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
  action?: string | ((formData: FormData) => void | Promise<void>);
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
  action,
}: OnboardingStepProps) {
  const cardContent = (
    <>
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
    </>
  );

  const className =
    "rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-8 shadow-sm sm:p-10";

  if (action) {
    return (
      <form action={action} className={className}>
        {cardContent}
      </form>
    );
  }

  return <div className={className}>{cardContent}</div>;
}
