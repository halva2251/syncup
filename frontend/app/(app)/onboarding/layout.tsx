import type { ReactNode } from "react";
import { OnboardingStepper } from "@/components/onboarding/stepper";

export default function OnboardingLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--color-bg-page)] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[640px]">
        <OnboardingStepper />
        {children}
      </div>
    </div>
  );
}
