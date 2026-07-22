"use client";

import { siDiscord } from "simple-icons";
import { useState, useTransition, type CSSProperties } from "react";
import { Plus, X } from "lucide-react";
import { AppIcon } from "@/components/ui/app-icon";
import {
  MANUAL_PROFILE_LINK_PLATFORMS,
  profileLinkPlatform,
  profileUsernameFromUrl,
  type ProfileLinkPlatform,
} from "@/lib/constants/profile-links";
import { addSocialLinkAction } from "@/lib/actions/settings-actions";

interface ProfileLinksProps {
  discordHandle: string | null;
  links: Record<string, string>;
  editable?: boolean;
}

function brandStyle(hex: string): CSSProperties {
  return { "--profile-link-brand": `#${hex}` } as CSSProperties;
}

function brandHex(hex: string | undefined) {
  return hex ?? "2563EB";
}

/** Public social and service links shown on a profile. */
export function ProfileLinks({ discordHandle, links, editable = false }: ProfileLinksProps) {
  const [currentLinks, setCurrentLinks] = useState(links);
  const [isAdding, setIsAdding] = useState(false);
  const [platform, setPlatform] = useState(MANUAL_PROFILE_LINK_PLATFORMS[0].id);
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const visibleLinks = Object.entries(currentLinks)
    .map(([platform, url]) => ({ platform: profileLinkPlatform(platform), url }))
    .filter(
      (link): link is { platform: ProfileLinkPlatform; url: string } =>
        link.platform !== undefined,
    );

  if (!discordHandle && visibleLinks.length === 0 && !editable) return null;

  const handleAddLink = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      const result = await addSocialLinkAction(platform, username);
      if ("error" in result) {
        setError(result.error ?? "Could not add this link. Please try again.");
        return;
      }
      setCurrentLinks((previous) => ({ ...previous, [result.platform]: result.url }));
      setUsername("");
      setIsAdding(false);
    });
  };

  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-text-primary)]">
        Links & social
      </h3>
      <div className="grid gap-2 sm:grid-cols-2">
        {discordHandle ? (
          <div
            className="profile-social-link flex min-w-0 items-center gap-3 rounded-lg border p-3"
            style={brandStyle(brandHex(siDiscord.hex))}
          >
            <AppIcon
              brand={siDiscord}
              size="xs"
              brandColor={`#${brandHex(siDiscord.hex)}`}
              iconSize={18}
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-[var(--color-text-primary)]">Discord</p>
              <p className="truncate text-xs text-[var(--color-text-secondary)]">{discordHandle}</p>
            </div>
          </div>
        ) : null}
        {visibleLinks.map(({ platform, url }) => (
          <a
            key={platform.id}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="profile-social-link flex min-w-0 items-center gap-3 rounded-lg border p-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            style={brandStyle(brandHex(platform.brand.hex))}
          >
            <AppIcon
              brand={platform.brand}
              size="xs"
              brandColor={`#${brandHex(platform.brand.hex)}`}
              iconSize={18}
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-[var(--color-text-primary)]">
                {platform.label}
              </p>
              {profileUsernameFromUrl(url) ? (
                <p className="truncate text-xs text-[var(--color-text-secondary)]">
                  {profileUsernameFromUrl(url)}
                </p>
              ) : null}
            </div>
          </a>
        ))}
        {editable && !isAdding ? (
          <button
            type="button"
            onClick={() => setIsAdding(true)}
            className="col-span-full inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] bg-transparent px-3.5 py-2 text-sm font-medium text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)]"
          >
            <Plus className="h-4 w-4" />
            Add links & social
          </button>
        ) : null}
        {editable && isAdding ? (
          <form
            onSubmit={handleAddLink}
            className="col-span-full rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-page)] p-4"
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <h4 className="text-sm font-medium text-[var(--color-text-primary)]">
                Add links & social
              </h4>
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setIsAdding(false);
                }}
                className="rounded-md p-1 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
                aria-label="Close social link form"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              <select
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
                className="h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 text-sm text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-[3px] focus:ring-[var(--color-accent-soft)]"
                aria-label="Social platform"
              >
                {MANUAL_PROFILE_LINK_PLATFORMS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Username"
                required
                className="h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:border-[var(--color-accent)] focus:outline-none focus:ring-[3px] focus:ring-[var(--color-accent-soft)]"
              />
            </div>
            {error ? (
              <p className="mt-3 text-xs text-[var(--color-danger)]">{error}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsAdding(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isPending}
                className="rounded-lg bg-[var(--color-accent)] px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isPending ? "Adding…" : "Add link"}
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </section>
  );
}
