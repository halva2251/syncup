import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Shield } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { PrivacyForm } from "@/components/settings/privacy-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Privacy & Matching · Settings · SyncUp",
};

export default async function PrivacySettingsPage() {
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
          icon={Shield}
          title="Privacy & Matching"
          description="Control whether you appear in match feeds and how you're surfaced to others."
        />

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] px-5 py-2 sm:px-6">
          <PrivacyForm initialIsMatchable={user.is_matchable} />
        </section>
      </div>
    </div>
  );
}
