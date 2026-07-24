import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { User } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { ProfileForm } from "@/components/settings/profile-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Profile · Settings · SyncUp",
};

export default async function ProfileSettingsPage() {
  let user;
  try {
    const me = await getCurrentUser();
    user = me.user;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={User}
          title="Profile"
          description="The details other people see on your taste card and match profile."
        />

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 sm:p-6">
          <ProfileForm
            initialDisplayName={user.display_name}
            initialBio={user.bio}
            initialDiscordHandle={user.discord_handle}
            initialAvatarUrl={user.avatar_url}
            initialLanguages={user.languages}
          />
        </section>
      </div>
    </div>
  );
}
