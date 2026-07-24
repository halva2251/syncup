import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { MatchScore } from "@/components/matches/match-score";
import { MatchHighlights } from "@/components/matches/match-highlights";
import type { Match } from "@/types/api";

interface MatchCardProps {
  match: Match;
}

/**
 * One entry in the discovery feed: avatar, name, bio, compatibility score,
 * shared highlights, and a matching-mode tag. The whole card links to the
 * match detail page.
 */
export function MatchCard({ match }: MatchCardProps) {
  const { user, score, shared_highlights } = match;

  return (
    <Link
      href={`/feed/${user.id}`}
      className="group flex items-start gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 transition-colors hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] sm:p-5"
    >
      <Avatar src={user.avatar_url} alt={user.display_name} size="lg" />

      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-[var(--color-text-primary)]">
              {user.display_name}
            </h3>
          </div>
          <MatchScore score={score} variant="compact" />
        </div>

        {user.bio ? (
          <p className="line-clamp-2 text-[13px] text-[var(--color-text-secondary)]">
            {user.bio}
          </p>
        ) : null}

        {shared_highlights.length > 0 ? (
          <MatchHighlights highlights={shared_highlights} variant="compact" />
        ) : null}
      </div>

      <ChevronRight
        className="mt-1 h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-text-primary)]"
        strokeWidth={2}
      />
    </Link>
  );
}
