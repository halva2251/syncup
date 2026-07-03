import { redirect } from "next/navigation";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { ApiError } from "@/lib/api/client";

export default async function IndexPage() {
  let status;

  try {
    status = await getOnboardingStatus();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  if (status.next_step === "set_display_name") {
    redirect("/onboarding/profile");
  }

  if (status.next_step === "connect_service") {
    redirect("/onboarding/services");
  }

  if (status.next_step === "set_matchable") {
    redirect("/onboarding/taste");
  }

  redirect("/home");
}
