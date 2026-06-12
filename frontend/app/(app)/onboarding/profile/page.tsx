import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ProfileStepForm } from "@/components/onboarding/profile-step-form";

export default async function OnboardingProfilePage() {
  let user;
  let status;

  try {
    const me = await getCurrentUser();
    user = me.user;
    status = await getOnboardingStatus();
  } catch {
    redirect("/login");
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return <ProfileStepForm languages={user.languages} />;
}
