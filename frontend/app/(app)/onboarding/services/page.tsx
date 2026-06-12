import Link from "next/link";
import { ButtonLink } from "@/components/ui/button";

export default function OnboardingServicesPage() {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Connect your services
        </h1>
        <p className="mt-1 text-[15px] text-[var(--color-text-secondary)]">
          Link accounts like Spotify, Steam, or Last.fm to improve your matches.
          This step is coming soon — you can skip it for now.
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-6 text-center">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Service connection UI will be built here next.
        </p>
        <Link
          href="/onboarding/obsessions"
          className="mt-2 inline-block text-sm font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
        >
          Add manual obsessions instead →
        </Link>
      </div>

      <div className="mt-8 flex items-center justify-between gap-3">
        <ButtonLink
          href="/onboarding/profile"
          variant="secondary"
          size="lg"
          className="bg-[var(--color-bg-card)]"
        >
          Back
        </ButtonLink>
        <ButtonLink href="/onboarding/obsessions" size="lg">
          Continue
        </ButtonLink>
      </div>
    </div>
  );
}
