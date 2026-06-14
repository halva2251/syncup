import { redirect } from "next/navigation";
import { listObsessions } from "@/lib/api/obsessions";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ObsessionsStepForm } from "@/components/onboarding/obsessions-step-form";

export default async function OnboardingObsessionsPage() {
  let user;
  let status;
  let obsessions;

  try {
    const [me, onboardingStatus, obsessionsList] = await Promise.all([
      getCurrentUser(),
      getOnboardingStatus(),
      listObsessions(),
    ]);
    user = me.user;
    status = onboardingStatus;
    obsessions = obsessionsList;
  } catch {
    redirect("/login");
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return (
    <ObsessionsStepForm
      initialObsessions={obsessions}
      key={user.id}
    />
  );
}
