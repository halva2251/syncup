import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { listOverrides } from "@/lib/api/overrides";
import { SettingsPageHeader } from "@/components/settings/settings-page-header";
import { PreferenceOverridesEditor } from "@/components/taste/preference-overrides-editor";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Taste Controls · Settings · SyncUp",
};

export default async function TasteSettingsPage() {
  let overrides;
  try {
    overrides = await listOverrides();
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
          icon={SlidersHorizontal}
          title="Taste Controls"
          description="Boost or dampen specific items to shape how they influence your matches and recommendations."
        />

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
          <PreferenceOverridesEditor initialOverrides={overrides} />
        </section>

        <p className="text-xs text-[var(--color-text-tertiary)]">
          Excluding individual items lives on your{" "}
          <a
            href="/taste"
            className="text-[var(--color-accent)] underline-offset-2 hover:underline"
          >
            taste card
          </a>
          . Per-service weighting lives in{" "}
          <a
            href="/settings/dimensions"
            className="text-[var(--color-accent)] underline-offset-2 hover:underline"
          >
            dimensions
          </a>
          .
        </p>
      </div>
    </div>
  );
}
