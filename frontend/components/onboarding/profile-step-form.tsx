"use client";

import { useActionState, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { LanguageSelect } from "@/components/ui/language-select";
import { Loader2, Languages } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
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
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-8 flex items-start gap-4">
        <AppIcon icon={Languages} size="md" gradient="brand" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Welcome to SyncUp
          </h1>
          <p className="mt-1 text-[15px] text-[var(--color-text-secondary)]">
            Let&apos;s set up your profile. You can always change this later.
          </p>
        </div>
      </div>

      <form action={formAction} className="space-y-5">
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

        <Button
          type="submit"
          size="lg"
          className="mt-2 w-full"
          disabled={pending}
        >
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          Continue
        </Button>
      </form>
    </div>
  );
}
