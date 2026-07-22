import { MessageCircle } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { MatchScore } from "@/components/matches/match-score";
import { MatchHighlights } from "@/components/matches/match-highlights";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import type { Match } from "@/types/api";

interface MatchDetailProps {
  match: Match;
  /** Hide match-only information when rendering the signed-in user's profile. */
  showCompatibility?: boolean;
}

/** One breakdown bar: service name + proportional fill. */
function BreakdownBar({
  serviceId,
  value,
}: {
  serviceId: string;
  value: number;
}) {
  const service = SERVICE_BY_ID.get(serviceId);
  const name = service?.name ?? serviceId;
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-[var(--color-text-secondary)]">
          {name}
        </span>
        <span className="text-[var(--color-text-tertiary)]">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-border-subtle)]">
        <div
          className="h-full rounded-full bg-[var(--color-accent)]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Full profile detail for a single matched user. Shows the match metadata
 * (score, breakdown, shared highlights) and the Discord handle for connecting.
 */
export function MatchDetail({ match, showCompatibility = true }: MatchDetailProps) {
  const { user, score, breakdown, shared_highlights } = match;
  const breakdownEntries = Object.entries(breakdown).filter(
    ([serviceId]) => serviceId !== "combined",
  );

  return (
    <div className="space-y-6">
      {/* Identity header */}
      <section className="flex items-start gap-4">
        <Avatar src={user.avatar_url} alt={user.display_name} size="xl" />
        <div className="min-w-0 space-y-1 pt-1">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
            {user.display_name}
          </h2>
          {user.bio ? (
            <p className="pt-1 text-sm leading-relaxed text-[var(--color-text-secondary)]">
              {user.bio}
            </p>
          ) : null}
        </div>
      </section>

      {/* Compatibility */}
      {showCompatibility ? (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <MatchScore score={score} variant="detail" />
          {breakdownEntries.length > 0 ? (
            <div className="mt-4 space-y-3 border-t border-[var(--color-border-subtle)] pt-4">
              <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
                By service
              </h3>
              {breakdownEntries.map(([serviceId, value]) => (
                <BreakdownBar
                  key={serviceId}
                  serviceId={serviceId}
                  value={value}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* Shared highlights */}
      {shared_highlights.length > 0 ? (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">
            Taste you share
          </h3>
          <MatchHighlights highlights={shared_highlights} variant="detail" />
        </section>
      ) : null}

      {/* Discord handle */}
      {user.discord_handle ? (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <h3 className="mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
            Connect on Discord
          </h3>
          <div className="flex items-center gap-2 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-page)] px-3 py-2">
            <MessageCircle className="h-4 w-4 shrink-0 text-[var(--color-text-tertiary)]" />
            <code className="text-sm text-[var(--color-text-primary)]">
              {user.discord_handle}
            </code>
          </div>
          <p className="mt-2 text-xs text-[var(--color-text-tertiary)]">
            Reach out to start a conversation.
          </p>
        </section>
      ) : null}
    </div>
  );
}
