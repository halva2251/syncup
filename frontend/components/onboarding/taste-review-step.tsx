"use client";

import { useActionState } from "react";
import { Sparkles } from "lucide-react";
import { OnboardingStep } from "@/components/onboarding/onboarding-step";
import { TasteCard } from "@/components/taste/taste-card";
import { ErrorMessage } from "@/components/ui/error-message";
import { enableMatchingAction } from "@/lib/actions/taste-actions";
import type { TasteResponse, User } from "@/types/api";

interface TasteReviewStepProps {
  taste: TasteResponse;
  user: Pick<User, "archetype" | "vibe_summary" | "key_themes">;
}

export function TasteReviewStep({ taste, user }: TasteReviewStepProps) {
  const [state, formAction, pending] = useActionState(async () => {
    return await enableMatchingAction();
  }, null);

  return (
    <form action={formAction}>
      <OnboardingStep
        icon={Sparkles}
        title="Your taste card"
        description="See what we’ve learned about your taste. Start matching when you’re ready to find your people."
        backHref="/onboarding/obsessions"
        continueButton={{
          type: "submit",
          disabled: pending,
          loading: pending,
          "aria-busy": pending,
          children: "Find my matches",
        }}
      >
        {state?.error && (
          <ErrorMessage className="mb-5">{state.error}</ErrorMessage>
        )}
        <TasteCard taste={taste} user={user} />
      </OnboardingStep>
    </form>
  );
}
