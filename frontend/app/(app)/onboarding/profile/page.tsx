import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ProfileStepForm } from "@/components/onboarding/profile-step-form";

export default async function OnboardingProfilePage() {
  let user;
  let status;

  try {
    const [me, onboardingStatus] = await Promise.all([
      getCurrentUser(),
      getOnboardingStatus(),
    ]);
    user = me.user;
    status = onboardingStatus;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return <ProfileStepForm languages={user.languages} />;
}
