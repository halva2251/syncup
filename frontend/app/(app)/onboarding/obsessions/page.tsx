import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
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
    <ObsessionsStepForm
      initialObsessions={obsessions}
      key={user.id}
    />
  );
}
