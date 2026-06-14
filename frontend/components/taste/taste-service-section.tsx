import { AppIcon } from "@/components/ui/app-icon";
import { TasteItemList } from "@/components/taste/taste-item-list";
import { SERVICE_BY_ID } from "@/lib/constants/services";
import type { TasteItem, TasteServiceData } from "@/types/api";

interface TasteServiceSectionProps {
  serviceId: string;
  data: TasteServiceData;
  bordered?: boolean;
}

const BUCKET_LABELS: Record<string, string> = {
  top_games: "Top games",
  top_artists: "Top artists",
  top_tracks: "Top tracks",
  top_albums: "Top albums",
  top_films: "Top films",
  top_shows: "Top shows",
  top_anime: "Top anime",
  top_manga: "Top manga",
  top_communities: "Top communities",
};

function getItemLabel(serviceId: string, bucket: string, item: TasteItem): string {
  if (serviceId === "rateyourmusic" && item.artist) {
    return `${item.name} - ${item.artist}`;
  }
  if (bucket === "top_tracks") {
    if (item.artist) return `${item.name} - ${item.artist}`;
    if (item.artists && item.artists.length > 0) {
      return `${item.name} - ${item.artists.join(", ")}`;
    }
  }
  return item.name;
}

function getRankMode(serviceId: string): "index" | "score" | "rating" | "none" {
  if (serviceId === "rateyourmusic") return "rating";
  return "index";
}

export function TasteServiceSection({
  serviceId,
  data,
  bordered = true,
}: TasteServiceSectionProps) {
  const service = SERVICE_BY_ID.get(serviceId);
  const buckets = Object.entries(data).filter(
    ([, items]) => Array.isArray(items) && items.length > 0,
  );

  if (buckets.length === 0) return null;

  const isSingleBucket = buckets.length === 1;
  const rankMode = getRankMode(serviceId);

  const content = (
    <>
      <div className="mb-3 flex items-center gap-2.5">
        {service ? (
          <AppIcon
            brand={service.brand}
            size="sm"
            brandColor={`#${service.brand.hex}`}
          />
        ) : null}
        <h3 className="font-semibold text-[var(--color-text-primary)]">
          {service?.name ?? serviceId}
        </h3>
      </div>

      <div className={isSingleBucket ? undefined : "grid grid-cols-1 gap-4 sm:grid-cols-2"}>
        {buckets.map(([bucket, items]) => (
          <div key={bucket}>
            <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
              {BUCKET_LABELS[bucket] ?? bucket}
            </h4>
            <TasteItemList
              items={items.slice(0, 5)}
              rankMode={rankMode}
              getLabel={(item) => getItemLabel(serviceId, bucket, item)}
              excludable
            />
          </div>
        ))}
      </div>
    </>
  );

  if (!bordered) {
    return content;
  }

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4">
      {content}
    </div>
  );
}
