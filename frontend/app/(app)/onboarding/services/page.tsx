import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ServicesStepForm } from "@/components/onboarding/services-step-form";

export default async function OnboardingServicesPage() {
  let user;
  let status;
  let connections;

  try {
    const [me, onboardingStatus] = await Promise.all([
      getCurrentUser(),
      getOnboardingStatus(),
    ]);
    user = me.user;
    status = onboardingStatus;
    connections = me.connections;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return <ServicesStepForm initialConnections={connections} key={user.id} />;
}
