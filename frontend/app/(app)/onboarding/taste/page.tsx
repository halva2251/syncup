import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { getTasteProfile } from "@/lib/api/taste";
import { TasteReviewStep } from "@/components/onboarding/taste-review-step";

export default async function OnboardingTastePage() {
  let user;
  let status;
  let taste;

  try {
    const [me, onboardingStatus, tasteProfile] = await Promise.all([
      getCurrentUser(),
      getOnboardingStatus(),
      getTasteProfile(),
    ]);
    user = me.user;
    status = onboardingStatus;
    taste = tasteProfile;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return (
    <TasteReviewStep
      taste={taste}
      user={{
        archetype: user.archetype,
        vibe_summary: user.vibe_summary,
        key_themes: user.key_themes,
      }}
      key={user.id}
    />
  );
}
