"use client";

import { useActionState, useState } from "react";
import { ErrorMessage } from "@/components/ui/error-message";
import { LanguageSelect } from "@/components/ui/language-select";
import { OnboardingStep } from "@/components/onboarding/onboarding-step";
import { Loader2, Languages } from "lucide-react";
import { updateOnboardingProfile } from "@/lib/actions/profile-actions";

interface ProfileStepFormProps {
  languages: string[] | null;
}

export function ProfileStepForm({ languages }: ProfileStepFormProps) {
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(
    languages ?? [],
  );

  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string } | null, formData: FormData) => {
      return await updateOnboardingProfile(formData);
    },
    null,
  );

  return (
    <OnboardingStep
      icon={Languages}
      title="Welcome to SyncUp"
      description="Let's set up your profile. You can always change this later."
      action={formAction}
      continueButton={{
        type: "submit",
        disabled: pending,
        children: (
          <>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Continue
          </>
        ),
      }}
    >
      <div className="space-y-5">
        {state?.error && <ErrorMessage>{state.error}</ErrorMessage>}

        <LanguageSelect
          name="languages"
          label="Languages you speak (optional)"
          selected={selectedLanguages}
          onChange={setSelectedLanguages}
          placeholder="Search languages..."
        />

        <p className="text-[13px] text-[var(--color-text-tertiary)]">
          This helps us match you with people you can actually talk to.
        </p>
      </div>
    </OnboardingStep>
  );
}
