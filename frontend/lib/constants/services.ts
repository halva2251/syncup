import {
  siSpotify,
  siSteam,
  siLastdotfm,
  siLetterboxd,
  siAnilist,
  siTrakt,
  siReddit,
  siMusicbrainz,
} from "simple-icons";
import type { SimpleIcon } from "simple-icons";

export type ConnectionType = "oauth" | "username" | "csv" | "oauth_or_username";

export interface ServiceMeta {
  id: string;
  name: string;
  type: ConnectionType;
  brand: SimpleIcon;
  description: string;
  oauthStartUrl?: string;
  csvLabel?: string;
}

export const SERVICES: ServiceMeta[] = [
  {
    id: "spotify",
    name: "Spotify",
    type: "oauth",
    brand: siSpotify,
    description: "Top artists and tracks",
    oauthStartUrl: "/api/auth/spotify",
  },
  {
    id: "steam",
    name: "Steam",
    type: "oauth_or_username",
    brand: siSteam,
    description: "Games and playtime",
    oauthStartUrl: "/api/connect/steam/openid/start",
  },
  {
    id: "lastfm",
    name: "Last.fm",
    type: "oauth_or_username",
    brand: siLastdotfm,
    description: "Top artists and scrobbles",
    oauthStartUrl: "/api/connect/lastfm/oauth/start",
  },
  {
    id: "letterboxd",
    name: "Letterboxd",
    type: "csv",
    brand: siLetterboxd,
    description: "Film diary export",
    csvLabel: "Import Letterboxd diary CSV",
  },
  {
    id: "anilist",
    name: "AniList",
    type: "oauth",
    brand: siAnilist,
    description: "Anime and manga",
    oauthStartUrl: "/api/connect/anilist/oauth/start",
  },
  {
    id: "trakt",
    name: "Trakt",
    type: "oauth",
    brand: siTrakt,
    description: "Movies and shows",
    oauthStartUrl: "/api/connect/trakt/oauth/start",
  },
  {
    id: "reddit",
    name: "Reddit",
    type: "oauth",
    brand: siReddit,
    description: "Subreddit subscriptions",
    oauthStartUrl: "/api/connect/reddit/oauth/start",
  },
  {
    id: "rateyourmusic",
    name: "RateYourMusic",
    type: "csv",
    brand: siMusicbrainz,
    description: "Album ratings export",
    csvLabel: "Import RYM ratings CSV",
  },
];

export const SERVICE_BY_ID = new Map(SERVICES.map((s) => [s.id, s]));
