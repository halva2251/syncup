import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { getTasteProfile } from "@/lib/api/taste";
import { TasteReviewStep } from "@/components/onboarding/taste-review-step";

export default async function OnboardingTastePage() {
  let user;
  let status;
  let taste;

  try {
    const me = await getCurrentUser();
    user = me.user;
    status = await getOnboardingStatus();
    taste = await getTasteProfile();
  } catch {
    redirect("/login");
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
