"use server";

import { revalidatePath } from "next/cache";
import {
  createOverride,
  updateOverride,
  deleteOverride,
  type CreateOverrideInput,
  type UpdateOverrideInput,
} from "@/lib/api/overrides";
import { ApiError } from "@/lib/api/client";
import type { PreferenceOverride } from "@/types/api";

function safeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

export type OverrideActionResult =
  | { override: PreferenceOverride; error?: never }
  | { error: string; override?: never };

export type OverrideDeleteResult =
  | { success: true; error?: never }
  | { error: string; success?: never };

const BOOST_MIN = 0.1;
const BOOST_MAX = 10;

function validateBoost(value: number): string | null {
  if (!Number.isFinite(value)) return "Enter a number.";
  if (value < BOOST_MIN) return `Boost must be at least ${BOOST_MIN}.`;
  if (value > BOOST_MAX) return `Boost must be ${BOOST_MAX} or less.`;
  return null;
}

export async function createOverrideAction(
  input: CreateOverrideInput,
): Promise<OverrideActionResult> {
  const boostError = validateBoost(input.boost_multiplier);
  if (boostError) return { error: boostError };
  if (!input.item_id.trim()) {
    return { error: "Item ID is required." };
  }

  try {
    const override = await createOverride({
      item_id: input.item_id.trim(),
      boost_multiplier: input.boost_multiplier,
      note: input.note?.trim() ? input.note.trim() : null,
    });
    revalidatePath("/settings/taste");
    return { override };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function updateOverrideAction(
  id: string,
  input: UpdateOverrideInput,
): Promise<OverrideActionResult> {
  if (input.boost_multiplier !== undefined) {
    const boostError = validateBoost(input.boost_multiplier);
    if (boostError) return { error: boostError };
  }

  const body: UpdateOverrideInput = {};
  if (input.boost_multiplier !== undefined) {
    body.boost_multiplier = input.boost_multiplier;
  }
  if (input.note !== undefined) {
    body.note = input.note?.trim() ? input.note.trim() : null;
  }

  try {
    const override = await updateOverride(id, body);
    revalidatePath("/settings/taste");
    return { override };
  } catch (err) {
    return { error: safeError(err) };
  }
}

export async function deleteOverrideAction(
  id: string,
): Promise<OverrideDeleteResult> {
  try {
    await deleteOverride(id);
  } catch (err) {
    return { error: safeError(err) };
  }
  revalidatePath("/settings/taste");
  return { success: true };
}

