"use server";

import { revalidatePath } from "next/cache";
import {
  connectSteam,
  connectLastfm,
  importCsv,
  triggerSync,
} from "@/lib/api/connections";
import { getCurrentUser } from "@/lib/api/me";
import { ApiError } from "@/lib/api/client";
import type { ServiceConnection } from "@/types/api";

function safeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

export async function refreshConnections(): Promise<ServiceConnection[]> {
  const me = await getCurrentUser();
  return me.connections;
}

export async function connectSteamAction(formData: FormData) {
  const input = formData.get("steam_input") as string;
  if (!input || !input.trim()) {
    return { error: "Enter a Steam ID or vanity URL." };
  }

  const value = input.trim();
  const body = /^\d+$/.test(value)
    ? { steam_id: value }
    : { vanity_url: value };

  try {
    const connection = await connectSteam(body);
    await triggerSync(connection.service);
    revalidatePath("/onboarding/services");
    return { connection };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function connectLastfmAction(formData: FormData) {
  const username = formData.get("lastfm_username") as string;
  if (!username || !username.trim()) {
    return { error: "Enter a Last.fm username." };
  }

  try {
    const connection = await connectLastfm({ username: username.trim() });
    await triggerSync(connection.service);
    revalidatePath("/onboarding/services");
    return { connection };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function importCsvAction(service: string, formData: FormData) {
  const file = formData.get("file") as File | null;
  if (!file || file.size === 0) {
    return { error: "Please select a CSV file." };
  }

  try {
    const result = await importCsv(service, file);
    revalidatePath("/onboarding/services");
    return result;
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function triggerSyncAction(service: string) {
  try {
    const result = await triggerSync(service);
    revalidatePath("/onboarding/services");
    return result;
  } catch (err) {
    return { error: safeError(err) };
  }
}
