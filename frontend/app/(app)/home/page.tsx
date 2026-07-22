import type { Metadata } from "next";
import { redirect } from "next/navigation";
import {
  Home as HomeIcon,
  Sparkles,
  Plug,
  Heart,
  Users,
  Compass,
  ChevronRight,
  Lightbulb,
  type LucideIcon,
} from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser } from "@/lib/api/me";
import { getMatchSummary } from "@/lib/api/matches";
import { getTasteProfile } from "@/lib/api/taste";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { ButtonLink } from "@/components/ui/button";
import { AppIcon, type AppIconGradient } from "@/components/ui/app-icon";
import type {
  MatchSummary,
  MeResponse,
  TasteResponse,
  ServiceConnection,
} from "@/types/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Home · SyncUp",
};

/** Count total top-items across every bucket of every service in the taste profile. */
function countTasteItems(taste: TasteResponse): number {
  let total = 0;
  for (const data of Object.values(taste.services)) {
    total +=
      (data.top_games?.length ?? 0) +
      (data.top_artists?.length ?? 0) +
      (data.top_tracks?.length ?? 0) +
      (data.top_albums?.length ?? 0) +
      (data.top_films?.length ?? 0) +
      (data.top_shows?.length ?? 0) +
      (data.top_anime?.length ?? 0) +
      (data.top_manga?.length ?? 0) +
      (data.top_communities?.length ?? 0);
  }
  return total;
}

function formatStatus(status: string): string {
  switch (status) {
    case "ok":
      return "Connected";
    case "pending":
      return "Pending";
    case "syncing":
      return "Syncing";
    case "error":
      return "Error";
    default:
      return "Not connected";
  }
}

function statusDotClass(status: string): string {
  switch (status) {
    case "ok":
      return "bg-[var(--color-success)]";
    case "pending":
    case "syncing":
      return "bg-[var(--color-warning)]";
    case "error":
      return "bg-[var(--color-danger)]";
    default:
      return "bg-[var(--color-text-tertiary)]";
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface QuickLink {
  href: string;
  icon: LucideIcon;
  gradient: AppIconGradient;
  title: string;
  description: string;
}

const QUICK_LINKS: QuickLink[] = [
  {
    href: "/taste",
    icon: Sparkles,
    gradient: "brand",
    title: "Your Taste",
    description: "View and share your taste card.",
  },
  {
    href: "/connections",
    icon: Plug,
    gradient: "orange",
    title: "Connections",
    description: "Connect or sync your platforms.",
  },
  {
    href: "/matches",
    icon: Users,
    gradient: "purple",
    title: "Matches",
    description: "Browse people with compatible taste.",
  },
  {
    href: "/recommendations",
    icon: Compass,
    gradient: "green",
    title: "Recommendations",
    description: "Discover new things across your domains.",
  },
];

export default async function HomePage() {
  let me: MeResponse;
  let taste: TasteResponse;
  let matchSummary: MatchSummary;
  try {
    [me, taste, matchSummary] = await Promise.all([
      getCurrentUser(),
      getTasteProfile(),
      getMatchSummary(),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  const { user, connections } = me;

  const connectedCount = connections.length;
  const tasteItemCount = countTasteItems(taste);
  const obsessionCount = taste.manual_obsessions.length;
  const hasTasteData =
    tasteItemCount > 0 || obsessionCount > 0 || taste.overrides.length > 0;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
      <div className="space-y-8">
        <PageHeader
          icon={HomeIcon}
          title={`Welcome back, ${user.display_name.split(" ")[0]}`}
          description="Your SyncUp dashboard — taste, matches, and connections at a glance."
        />

        {/* Stat overview row */}
        <section
          aria-label="Overview"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <StatCard
            icon={Plug}
            gradient="orange"
            label="Services"
            value={connectedCount}
          />
          <StatCard
            icon={Sparkles}
            gradient="brand"
            label="Taste items"
            value={tasteItemCount}
          />
          <StatCard
            icon={Heart}
            gradient="red"
            label="Obsessions"
            value={obsessionCount}
          />
          <StatCard
            icon={Users}
            gradient="purple"
            label="Matches found"
            value={matchSummary.count}
          />
        </section>

        {/* Vibe summary (when available) */}
        {user.archetype || user.vibe_summary ? (
          <section className="rounded-xl border border-[var(--color-border)] bg-gradient-to-br from-[var(--color-accent-soft)] to-[var(--color-bg-card)] p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <AppIcon icon={Sparkles} size="sm" gradient="brand" />
              <div className="min-w-0 space-y-1">
                {user.archetype ? (
                  <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
                    {user.archetype}
                  </h2>
                ) : null}
                {user.vibe_summary ? (
                  <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
                    {user.vibe_summary}
                  </p>
                ) : null}
                {user.key_themes && user.key_themes.length > 0 ? (
                  <p className="text-xs text-[var(--color-text-tertiary)]">
                    {user.key_themes.join(" · ")}
                  </p>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        {/* Onboarding nudges / empty states */}
        {!hasTasteData ? (
          <section className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-10 text-center">
            <Plug className="mx-auto h-10 w-10 text-[var(--color-text-tertiary)]" />
            <h2 className="mt-4 text-base font-medium text-[var(--color-text-primary)]">
              Let&apos;s build your taste profile
            </h2>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-[var(--color-text-secondary)]">
              Connect a platform or add a few obsessions so SyncUp can find your
              best matches.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <ButtonLink href="/connections">Connect a service</ButtonLink>
              <ButtonLink href="/onboarding/obsessions" variant="secondary">
                Add obsessions
              </ButtonLink>
            </div>
          </section>
        ) : null}

        {/* Quick links grid */}
        <nav aria-label="Quick links" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {QUICK_LINKS.map((link) => (
            <ButtonLink
              key={link.href}
              href={link.href}
              variant="secondary"
              className="group !flex h-auto items-start justify-start gap-4 border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 text-left hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-bg-page)]"
            >
              <AppIcon icon={link.icon} size="sm" gradient={link.gradient} />
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-[var(--color-text-primary)]">
                  {link.title}
                </h3>
                <p className="mt-0.5 text-[13px] font-normal text-[var(--color-text-secondary)]">
                  {link.description}
                </p>
              </div>
              <ChevronRight
                className="mt-1 h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-text-primary)]"
                strokeWidth={2}
              />
            </ButtonLink>
          ))}
        </nav>

        {/* Connected services status */}
        <ConnectionsCard connections={connections} />

        {/* Recommendations teaser — surfaces cross-domain recs once the page exists */}
        <RecommendationsTeaser hasTasteData={hasTasteData} />
      </div>
    </div>
  );
}

/** Connected-services status list with a link to /connections for management. */
function ConnectionsCard({ connections }: { connections: ServiceConnection[] }) {
  if (connections.length === 0) {
    return null;
  }
  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <Plug className="h-4 w-4 text-[var(--color-text-tertiary)]" />
          Connected services
        </h2>
        <ButtonLink href="/connections" variant="secondary" size="sm">
          Manage
        </ButtonLink>
      </div>
      <ul className="divide-y divide-[var(--color-border-subtle)]">
        {connections.map((connection) => {
          const service = SERVICE_BY_ID.get(connection.service);
          const name = service?.name ?? connection.service;
          return (
            <li
              key={connection.service}
              className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-center gap-3">
                {service ? (
                  <AppIcon
                    brand={service.brand}
                    size="xs"
                    brandColor={`#${service.brand.hex}`}
                  />
                ) : null}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[var(--color-text-primary)]">
                    {name}
                  </div>
                  <div className="truncate text-xs text-[var(--color-text-tertiary)]">
                    Last synced {formatTimestamp(connection.last_synced_at)}
                  </div>
                </div>
              </div>
              {connection.sync_status !== "ok" && (
                <span className="inline-flex items-center gap-1.5 self-start text-xs font-medium text-[var(--color-text-secondary)] sm:self-auto">
                  <span
                    className={`h-2 w-2 rounded-full ${statusDotClass(
                      connection.sync_status,
                    )}`}
                  />
                  {formatStatus(connection.sync_status)}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Recommendations teaser. The `/recommendations` page is not built yet, so this
 * surfaces a low-key nudge with a link rather than a broken empty list.
 */
function RecommendationsTeaser({ hasTasteData }: { hasTasteData: boolean }) {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div className="flex items-start gap-3">
        <AppIcon icon={Lightbulb} size="sm" gradient="green" />
        <div className="min-w-0 space-y-0.5">
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
            Looking for something new?
          </h2>
          <p className="text-[13px] text-[var(--color-text-secondary)]">
            Get cross-domain recommendations based on your taste.
          </p>
        </div>
      </div>
      <ButtonLink
        href="/recommendations"
        variant={hasTasteData ? "primary" : "secondary"}
        size="md"
        className="shrink-0"
      >
        Explore recommendations
      </ButtonLink>
    </section>
  );
}
