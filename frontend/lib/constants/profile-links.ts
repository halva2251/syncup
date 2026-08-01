import {
  siBluesky,
  siGithub,
  siInstagram,
  siMastodon,
  siSoundcloud,
  siTiktok,
  siTwitch,
  siX,
  siYoutube,
} from "simple-icons";
import type { SimpleIcon } from "@/components/ui/app-icon";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import type { ServiceConnection } from "@/types/api";

export interface ProfileLinkPlatform {
  id: string;
  label: string;
  brand: SimpleIcon;
}

export const MANUAL_PROFILE_LINK_PLATFORMS: ProfileLinkPlatform[] = [
  { id: "github", label: "GitHub", brand: siGithub },
  { id: "x", label: "X", brand: siX },
  { id: "instagram", label: "Instagram", brand: siInstagram },
  { id: "tiktok", label: "TikTok", brand: siTiktok },
  { id: "youtube", label: "YouTube", brand: siYoutube },
  { id: "twitch", label: "Twitch", brand: siTwitch },
  { id: "bluesky", label: "Bluesky", brand: siBluesky },
  { id: "mastodon", label: "Mastodon", brand: siMastodon },
  { id: "soundcloud", label: "SoundCloud", brand: siSoundcloud },
];

const MANUAL_PROFILE_URLS: Record<string, (username: string) => string> = {
  github: (username) => `https://github.com/${username}`,
  x: (username) => `https://x.com/${username}`,
  instagram: (username) => `https://www.instagram.com/${username}`,
  tiktok: (username) => `https://www.tiktok.com/@${username}`,
  youtube: (username) => `https://www.youtube.com/@${username}`,
  twitch: (username) => `https://www.twitch.tv/${username}`,
  bluesky: (username) => `https://bsky.app/profile/${username}`,
  mastodon: (username) => `https://mastodon.social/@${username}`,
  soundcloud: (username) => `https://soundcloud.com/${username}`,
};

/** Turn a supported platform username into its canonical public profile URL. */
export function profileUrlFromUsername(platform: string, username: string): string | null {
  const buildUrl = MANUAL_PROFILE_URLS[platform];
  if (!buildUrl) return null;
  const normalizedUsername = username.trim().replace(/^@/, "");
  return normalizedUsername ? buildUrl(encodeURIComponent(normalizedUsername)) : null;
}

/** Extract the visible account identifier from a canonical public profile URL. */
export function profileUsernameFromUrl(url: string): string | null {
  try {
    const segments = new URL(url).pathname.split("/").filter(Boolean);
    const username = segments.at(-1);
    return username ? decodeURIComponent(username) : null;
  } catch {
    return null;
  }
}

const SERVICE_PROFILE_URLS: Record<string, (externalId: string) => string> = {
  anilist: (id) => `https://anilist.co/user/${encodeURIComponent(id)}`,
  lastfm: (id) => `https://www.last.fm/user/${encodeURIComponent(id)}`,
  reddit: (id) => `https://www.reddit.com/user/${encodeURIComponent(id)}`,
  spotify: (id) => `https://open.spotify.com/user/${encodeURIComponent(id)}`,
  steam: (id) => `https://steamcommunity.com/profiles/${encodeURIComponent(id)}`,
  trakt: (id) => `https://trakt.tv/users/${encodeURIComponent(id)}`,
};

export function profileLinkPlatform(id: string): ProfileLinkPlatform | undefined {
  const manual = MANUAL_PROFILE_LINK_PLATFORMS.find((platform) => platform.id === id);
  if (manual) return manual;
  const service = SERVICE_BY_ID.get(id);
  return service
    ? { id: service.id, label: service.name, brand: service.brand }
    : undefined;
}

/** Add links inferred from services that expose a stable public profile URL. */
export function buildOwnProfileLinks(
  socialLinks: Record<string, string> | null,
  connections: ServiceConnection[],
) {
  const links = { ...(socialLinks ?? {}) };
  for (const connection of connections) {
    const buildUrl = SERVICE_PROFILE_URLS[connection.service];
    if (buildUrl) links[connection.service] = buildUrl(connection.external_user_id);
  }
  return links;
}
