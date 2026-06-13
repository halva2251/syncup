import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ButtonLink } from "@/components/ui/button";
import { GlossyButton, GlossyButtonLink } from "@/components/ui/glossy-button";

interface OnboardingActionsProps {
  backHref?: string;
  backLabel?: string;
  continueHref?: string;
  continueButton?: Omit<
    ButtonHTMLAttributes<HTMLButtonElement>,
    "className" | "children"
  > & {
    children?: ReactNode;
  };
  continueLabel?: ReactNode;
}

export function OnboardingActions({
  backHref,
  backLabel = "Back",
  continueHref,
  continueButton,
  continueLabel = "Continue",
}: OnboardingActionsProps) {
  const justifyClass = backHref ? "justify-between" : "justify-end";

  return (
    <div className={`mt-8 flex items-center gap-3 ${justifyClass}`}>
      {backHref && (
        <ButtonLink
          href={backHref}
          variant="secondary"
          size="lg"
          className="bg-[var(--color-bg-card)]"
        >
          {backLabel}
        </ButtonLink>
      )}

      {continueHref ? (
        <GlossyButtonLink
          href={continueHref}
          className={backHref ? undefined : "w-full"}
        >
          {continueLabel}
        </GlossyButtonLink>
      ) : continueButton ? (
        <GlossyButton
          {...continueButton}
          className={backHref ? undefined : "w-full"}
        >
          {continueButton.children ?? continueLabel}
        </GlossyButton>
      ) : null}
    </div>
  );
}
