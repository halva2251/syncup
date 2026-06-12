import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ServicesStepForm } from "@/components/onboarding/services-step-form";

export default async function OnboardingServicesPage() {
  let user;
  let status;
  let connections;

  try {
    const me = await getCurrentUser();
    user = me.user;
    status = await getOnboardingStatus();
    connections = me.connections;
  } catch {
    redirect("/login");
  }

  if (status.next_step === null) {
    redirect("/home");
  }

  return <ServicesStepForm initialConnections={connections} key={user.id} />;
}
