import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import {
  Settings as SettingsIcon,
  User,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Plug,
  ChevronRight,
  Mail,
  CalendarDays,
  LogOut,
  SunMoon,
} from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { AppIcon, type AppIconGradient } from "@/components/ui/app-icon";
import { Button } from "@/components/ui/button";
import { logoutAction } from "@/lib/actions/auth-actions";
import type { LucideIcon } from "lucide-react";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Settings · SyncUp",
};

interface SettingsCardDef {
  href: string;
  icon: LucideIcon;
  gradient: AppIconGradient;
  title: string;
  description: string;
}

const SETTINGS_CARDS: SettingsCardDef[] = [
  {
    href: "/settings/profile",
    icon: User,
    gradient: "blue",
    title: "Profile",
    description: "Your name, bio, Discord handle, and languages.",
  },
  {
    href: "/settings/privacy",
    icon: Shield,
    gradient: "purple",
    title: "Privacy & Matching",
    description: "Control who can match with you and see your profile.",
  },
  {
    href: "/settings/dimensions",
    icon: SlidersHorizontal,
    gradient: "green",
    title: "Taste Dimensions",
    description: "Weight how much each service influences your matches.",
  },
  {
    href: "/settings/taste",
    icon: Sparkles,
    gradient: "brand",
    title: "Taste Controls",
    description: "Boost or dampen specific items in your taste profile.",
  },
  {
    href: "/settings/services",
    icon: Plug,
    gradient: "orange",
    title: "Connected Services",
    description: "Sync status for your linked platforms.",
  },
  {
    href: "/settings/appearance",
    icon: SunMoon,
    gradient: "blue",
    title: "Appearance",
    description: "Choose light or dark mode across SyncUp.",
  },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default async function SettingsHubPage() {
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
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-6">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <AppIcon icon={SettingsIcon} size="xs" gradient="brand" />
            <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">
              Settings
            </h1>
          </div>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Manage your profile, privacy, taste, and connected services.
          </p>
        </div>

        {/* Account readout */}
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                {user.display_name}
              </h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[var(--color-text-secondary)]">
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-[var(--color-text-tertiary)]" />
                  {user.email}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="h-3.5 w-3.5 text-[var(--color-text-tertiary)]" />
                  Joined {formatDate(user.created_at)}
                </span>
              </div>
            </div>
            <span
              className={`inline-flex w-fit items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${
                user.is_matchable
                  ? "bg-[var(--color-tag-green-bg)] text-[var(--color-tag-green-text)]"
                  : "bg-[var(--color-tag-yellow-bg)] text-[var(--color-tag-yellow-text)]"
              }`}
            >
              {user.is_matchable ? "Matchable" : "Hidden from matches"}
            </span>
          </div>
        </section>

        {/* Settings cards grid */}
        <nav aria-label="Settings sections" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {SETTINGS_CARDS.map((card) => {
            return (
              <Link
                key={card.href}
                href={card.href}
                className="group flex items-start gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 transition-colors hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)]"
              >
                <AppIcon
                  icon={card.icon}
                  size="sm"
                  gradient={card.gradient}
                />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-[var(--color-text-primary)]">
                    {card.title}
                  </h3>
                  <p className="mt-0.5 text-[13px] text-[var(--color-text-secondary)]">
                    {card.description}
                  </p>
                </div>
                <ChevronRight
                  className="mt-1 h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-text-primary)]"
                  strokeWidth={2}
                />
              </Link>
            );
          })}
        </nav>

        <section className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
              Sign out
            </h2>
            <p className="mt-0.5 text-[13px] text-[var(--color-text-secondary)]">
              End this session on this device.
            </p>
          </div>
          <form action={logoutAction}>
            <Button variant="secondary" type="submit">
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Log out
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}
