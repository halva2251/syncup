import { Avatar } from "@/components/ui/avatar";
import { MatchScore } from "@/components/matches/match-score";
import { MatchHighlights } from "@/components/matches/match-highlights";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import { getLanguageFlag, getLanguageName } from "@/lib/constants/languages";
import { ProfileLinks } from "@/components/matches/profile-links";
import type { Match } from "@/types/api";

interface MatchDetailProps {
  match: Match;
  /** Hide match-only information when rendering the signed-in user's profile. */
  showCompatibility?: boolean;
  /** Show the signed-in user's inline social-link control. */
  editableLinks?: boolean;
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
 * (score, breakdown, shared highlights) and public social links for connecting.
 */
export function MatchDetail({
  match,
  showCompatibility = true,
  editableLinks = false,
}: MatchDetailProps) {
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
          {user.languages && user.languages.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-2">
              {user.languages.map((code) => {
                const flag = getLanguageFlag(code);
                return (
                  <span
                    key={code}
                    className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-xs font-medium text-[var(--color-accent)]"
                  >
                    {flag ? <span className={`fi fi-${flag} h-3 w-4 rounded-sm`} /> : null}
                    {getLanguageName(code) ?? code}
                  </span>
                );
              })}
            </div>
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

      <ProfileLinks
        discordHandle={user.discord_handle}
        links={user.profile_links}
        editable={editableLinks}
      />
    </div>
  );
}
