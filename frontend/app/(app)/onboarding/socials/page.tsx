import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getOnboardingStatus } from "@/lib/api/onboarding";
import { SocialLinksStep } from "@/components/onboarding/social-links-step";
import { buildOwnProfileLinks } from "@/lib/constants/profile-links";

export default async function OnboardingSocialLinksPage() {
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

  return (
    <SocialLinksStep
      discordHandle={user.discord_handle}
      links={buildOwnProfileLinks(user.social_links, connections)}
      key={user.id}
    />
  );
}
