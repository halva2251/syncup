import { apiFetch } from "@/lib/api/client";
import type { OnboardingStatus } from "@/types/api";

export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  return apiFetch<OnboardingStatus>("/onboarding/status");
}
