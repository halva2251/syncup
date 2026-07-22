"use client";

import { Share2 } from "lucide-react";
import { OnboardingStep } from "@/components/onboarding/onboarding-step";
import { ProfileLinks } from "@/components/matches/profile-links";

interface SocialLinksStepProps {
  discordHandle: string | null;
  links: Record<string, string>;
}

/** Optional onboarding step for adding public social and service-profile links. */
export function SocialLinksStep({ discordHandle, links }: SocialLinksStepProps) {
  return (
    <OnboardingStep
      icon={Share2}
      title="Add your social links"
      description="Give people a few more ways to find you. You can add or change these anytime."
      backHref="/onboarding/services"
      continueHref="/onboarding/obsessions"
      continueLabel="Continue"
    >
      <ProfileLinks
        discordHandle={discordHandle}
        links={links}
        editable
        showAddFormInitially
        keepAddFormOpen
        compactAddForm
      />
    </OnboardingStep>
  );
}
