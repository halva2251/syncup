export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  discord_handle: string | null;
  languages: string[] | null;
  is_matchable: boolean;
  onboarded: boolean;
  vibe_summary: string | null;
  archetype: string | null;
  key_themes: string[] | null;
  vibe_computed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceConnection {
  service: string;
  external_user_id: string;
  sync_status: "pending" | "syncing" | "ok" | "error";
  last_synced_at: string | null;
  token_expires_at: string | null;
  sync_error: string | null;
}

export interface MeResponse {
  user: User;
  connections: ServiceConnection[];
}

export interface OnboardingStatus {
  has_display_name: boolean;
  has_languages: boolean;
  has_connection_or_obsessions: boolean;
  has_taste_data: boolean;
  has_set_matchable: boolean;
  next_step: "set_display_name" | "connect_service" | "set_matchable" | null;
}

export interface TasteItem {
  id: string;
  name: string;
  score?: number;
  rating?: number;
  hours?: number;
  engagement_score?: number;
  artist?: string;
  artists?: string[];
  release_year?: number;
  play_count?: number;
}

export interface TasteItemChoice {
  id: string;
  name: string;
  service: string;
  item_type: string;
}

export interface ManualObsession {
  id: string;
  category: string;
  name: string;
  weight: number;
}

export interface PreferenceOverride {
  id: string;
  item: { id: string; name: string };
  boost_multiplier: number;
  note: string | null;
}

export interface TasteServiceData {
  top_games?: TasteItem[];
  top_artists?: TasteItem[];
  top_tracks?: TasteItem[];
  top_albums?: TasteItem[];
  top_films?: TasteItem[];
  top_shows?: TasteItem[];
  top_anime?: TasteItem[];
  top_manga?: TasteItem[];
  top_communities?: TasteItem[];
}

export interface TasteResponse {
  services: Record<string, TasteServiceData>;
  manual_obsessions: ManualObsession[];
  overrides: PreferenceOverride[];
}

export interface PublicTasteCardResponse {
  user: Pick<User, "archetype" | "vibe_summary" | "key_themes">;
  taste: TasteResponse;
}

export interface MatchUser {
  id: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  discord_handle: string | null;
}

export interface Match {
  user: MatchUser;
  score: number;
  breakdown: Record<string, number>;
  shared_highlights: { service: string; item_name: string }[];
  computed_at: string;
  matching_mode: "heuristic" | "semantic";
}

export interface MatchListResponse {
  items: Match[];
  next_cursor: string | null;
}

export interface MatchSummary {
  /** Number of fresh cached matches for the current user. */
  count: number;
}

export interface Recommendation {
  item_name: string;
  service: string;
  item_type: string;
  similarity_score: number;
}

export interface RecommendationsResponse {
  items: Recommendation[];
}
