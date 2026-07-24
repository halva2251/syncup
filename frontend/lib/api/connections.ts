import { apiFetch, ApiError } from "@/lib/api/client";
import { BACKEND_URL } from "@/lib/constants/backend-url";
import { cookies } from "next/headers";
import type { ServiceConnection } from "@/types/api";

export interface ConnectSteamInput {
  steam_id?: string;
  vanity_url?: string;
}

export interface ConnectLastfmInput {
  username: string;
}

export async function connectSteam(
  body: ConnectSteamInput
): Promise<ServiceConnection> {
  return apiFetch<ServiceConnection>("/connect/steam", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function connectLastfm(
  body: ConnectLastfmInput
): Promise<ServiceConnection> {
  return apiFetch<ServiceConnection>("/connect/lastfm", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function importCsv(
  service: string,
  file: File
): Promise<{ imported: number }> {
  const cookieStore = await cookies();
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${BACKEND_URL}/api/connect/${service}/import`, {
    method: "POST",
    headers: {
      Cookie: cookieStore.toString(),
    },
    body: formData,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      error?: { code: string; message: string };
    };
    const error = body.error;
    throw new ApiError(
      error?.code ?? "UNKNOWN_ERROR",
      error?.message ?? `Import failed with status ${response.status}`,
      response.status
    );
  }

  return response.json() as Promise<{ imported: number }>;
}

export async function triggerSync(
  service: string
): Promise<{ status: "syncing"; service: string; poll_url: string }> {
  return apiFetch<{ status: "syncing"; service: string; poll_url: string }>(
    `/sync/${service}`,
    {
      method: "POST",
    }
  );
}

export async function deleteConnection(service: string): Promise<void> {
  return apiFetch<void>(`/me/connections/${encodeURIComponent(service)}`, {
    method: "DELETE",
  });
}
