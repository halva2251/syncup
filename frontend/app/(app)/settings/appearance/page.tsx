import type { Metadata } from "next";
import { SunMoon } from "lucide-react";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { ThemeToggle } from "@/components/settings/theme-toggle";

export const metadata: Metadata = {
  title: "Appearance · Settings · SyncUp",
};

export default function AppearanceSettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <SettingsPageHeader
          icon={SunMoon}
          title="Appearance"
          description="Choose the color mode SyncUp uses across every page."
        />

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                Color mode
              </h2>
              <p className="text-[13px] text-[var(--color-text-secondary)]">
                Switch between light and dark mode at any time.
              </p>
            </div>
            <ThemeToggle />
          </div>
        </section>
      </div>
    </div>
  );
}
