import { redirect } from "next/navigation";
import { Sparkles, Settings, Plug } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getTasteProfile } from "@/lib/api/taste";
import { TasteCard } from "@/components/taste/taste-card";
import { ButtonLink } from "@/components/ui/button";
import { TasteActions } from "./taste-actions";

export const dynamic = "force-dynamic";

export default async function TastePage() {
  let user;
  let taste;
  let connectedServiceIds: string[] = [];

  try {
    const [me, tasteProfile] = await Promise.all([
      getCurrentUser(),
      getTasteProfile(),
    ]);
    user = me.user;
    taste = tasteProfile;
    connectedServiceIds = me.connections.map((connection) => connection.service);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  const serviceIds = Object.keys(taste.services);
  const hasAnyData =
    serviceIds.length > 0 ||
    taste.manual_obsessions.length > 0 ||
    taste.overrides.length > 0;

  // Construct the public taste card URL
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://syncup.app";
  const publicTasteUrl = `${appUrl}/u/${user.id}/taste`;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-[var(--color-accent)]" />
            <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">
              Your Taste
            </h1>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Your taste profile used for matching
          </p>
        </div>

        <div className="flex items-center gap-2">
          <TasteActions hasData={hasAnyData} publicTasteUrl={publicTasteUrl} />
          <ButtonLink variant="secondary" size="md" href="/onboarding/services" className="gap-2">
            <Plug className="h-4 w-4" />
            <span className="hidden sm:inline">Manage Services</span>
          </ButtonLink>
          <ButtonLink variant="secondary" size="md" href="/settings" className="gap-2">
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">Settings</span>
          </ButtonLink>
        </div>
      </div>

      {/* Taste Card */}
      {hasAnyData ? (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <TasteCard
            taste={taste}
            connectedServiceIds={connectedServiceIds}
            user={{
              archetype: user.archetype,
              vibe_summary: user.vibe_summary,
              key_themes: user.key_themes,
            }}
          />
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-12 text-center">
          <Sparkles className="mx-auto h-12 w-12 text-[var(--color-text-tertiary)]" />
          <h2 className="mt-4 text-lg font-medium text-[var(--color-text-primary)]">
            No taste data yet
          </h2>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            Connect a service or add obsessions to build your taste profile.
          </p>
          <ButtonLink variant="primary" size="lg" href="/onboarding/services" className="mt-6">
            Connect your first service
          </ButtonLink>
        </div>
      )}

      </div>
    </div>
  );
}
