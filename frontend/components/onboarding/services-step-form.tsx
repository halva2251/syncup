"use client";

import { Link2 } from "lucide-react";
import { OnboardingStep } from "@/components/onboarding/onboarding-step";
import { ServiceConnectGrid } from "@/components/connections/service-connect-grid";
import type { ServiceConnection } from "@/types/api";

interface ServicesStepFormProps {
  initialConnections: ServiceConnection[];
}

export function ServicesStepForm({
  initialConnections,
}: ServicesStepFormProps) {
  return (
    <OnboardingStep
      icon={Link2}
      title="Connect your services"
      description="Link the platforms where your taste actually lives. You can skip any service and add manual obsessions next."
      backHref="/onboarding/profile"
      continueHref="/onboarding/socials"
    >
      <ServiceConnectGrid initialConnections={initialConnections} />
    </OnboardingStep>
  );
}
