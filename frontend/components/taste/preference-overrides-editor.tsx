"use client";

import { useState, useTransition } from "react";
import { Loader2, X, SlidersHorizontal, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { toast } from "@/components/ui/toast";
import {
  createOverrideAction,
  updateOverrideAction,
  deleteOverrideAction,
} from "@/lib/actions/override-actions";
import type { PreferenceOverride } from "@/types/api";

interface PreferenceOverridesEditorProps {
  initialOverrides: PreferenceOverride[];
}

const BOOST_MIN = 0.1;
const BOOST_MAX = 10;
const BOOST_STEP = 0.1;

export function PreferenceOverridesEditor({
  initialOverrides,
}: PreferenceOverridesEditorProps) {
  const [overrides, setOverrides] = useState(initialOverrides);
  const [showCreate, setShowCreate] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  function handleCreated(override: PreferenceOverride) {
    setOverrides((prev) =>
      [...prev, override].sort((a, b) =>
        a.item.name.localeCompare(b.item.name),
      ),
    );
    setShowCreate(false);
  }

  function handleUpdated(id: string, next: PreferenceOverride) {
    setOverrides((prev) => prev.map((o) => (o.id === id ? next : o)));
  }

  async function handleDelete(id: string) {
    const previous = overrides;
    setPendingDeleteId(id);
    setOverrides((prev) => prev.filter((o) => o.id !== id));
    const result = await deleteOverrideAction(id);
    setPendingDeleteId(null);
    if ("error" in result && result.error) {
      setOverrides(previous); // rollback
      toast.error(result.error);
      return;
    }
    toast.success("Override removed");
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[13px] text-[var(--color-text-secondary)]">
          {overrides.length}{" "}
          {overrides.length === 1 ? "override" : "overrides"} — amplify how much
          an item contributes to your taste vector.
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setShowCreate((s) => !s)}
          className="gap-1.5"
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </Button>
      </div>

      {showCreate && (
        <CreateOverrideForm
          onCreated={handleCreated}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {overrides.length === 0 && !showCreate ? (
        <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-bg-page)] p-6 text-center">
          <SlidersHorizontal className="mx-auto h-8 w-8 text-[var(--color-text-tertiary)]" />
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            No overrides yet. Boost an item to make it count more, or dampen one
            you don&apos;t want steering matches.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {overrides.map((override) => (
            <OverrideRow
              key={override.id}
              override={override}
              deleting={pendingDeleteId === override.id}
              onUpdated={(next) => handleUpdated(override.id, next)}
              onDelete={() => handleDelete(override.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface OverrideRowProps {
  override: PreferenceOverride;
  deleting: boolean;
  onUpdated: (next: PreferenceOverride) => void;
  onDelete: () => void;
}

function OverrideRow({
  override,
  deleting,
  onUpdated,
  onDelete,
}: OverrideRowProps) {
  const [pending, startTransition] = useTransition();
  const [noteDraft, setNoteDraft] = useState(override.note ?? "");

  function commitBoost(value: number) {
    if (value === override.boost_multiplier || pending) return;
    startTransition(async () => {
      const result = await updateOverrideAction(override.id, {
        boost_multiplier: value,
      });
      if ("override" in result && result.override) {
        onUpdated(result.override);
        toast.success("Boost updated");
      } else if ("error" in result && result.error) {
        toast.error(result.error);
      }
    });
  }

  function commitNote() {
    const trimmed = noteDraft.trim();
    if (trimmed === (override.note ?? "").trim() || pending) return;
    startTransition(async () => {
      const result = await updateOverrideAction(override.id, { note: trimmed });
      if ("override" in result && result.override) {
        onUpdated(result.override);
      } else if ("error" in result && result.error) {
        toast.error(result.error);
      }
    });
  }

  return (
    <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-page)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="truncate text-sm font-medium text-[var(--color-text-primary)]">
            {override.item.name}
          </h4>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--color-text-tertiary)]">
            {override.item.id}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-14 text-right text-sm font-medium tabular-nums text-[var(--color-accent)]">
            ×{override.boost_multiplier.toFixed(1)}
          </span>
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            aria-label={`Remove override for ${override.item.name}`}
            className="rounded-md p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-danger)] disabled:opacity-50"
          >
            {deleting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <X className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <input
          type="range"
          min={BOOST_MIN}
          max={BOOST_MAX}
          step={BOOST_STEP}
          defaultValue={override.boost_multiplier}
          onMouseUp={(e) => commitBoost(Number(e.currentTarget.value))}
          onTouchEnd={(e) => commitBoost(Number(e.currentTarget.value))}
          disabled={pending}
          aria-label={`Boost multiplier for ${override.item.name}`}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--color-border)] accent-[var(--color-accent)]"
        />
      </div>

      <Input
        label="Note (optional)"
        value={noteDraft}
        onChange={(e) => setNoteDraft(e.target.value)}
        onBlur={commitNote}
        placeholder="Why this boost?"
        maxLength={500}
        disabled={pending}
        className="mt-3"
      />
    </li>
  );
}

interface CreateOverrideFormProps {
  onCreated: (override: PreferenceOverride) => void;
  onCancel: () => void;
}

function CreateOverrideForm({ onCreated, onCancel }: CreateOverrideFormProps) {
  const [itemId, setItemId] = useState("");
  const [boost, setBoost] = useState(1);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    startTransition(async () => {
      const result = await createOverrideAction({
        item_id: itemId,
        boost_multiplier: boost,
        note: note.trim() || null,
      });
      if ("override" in result && result.override) {
        onCreated(result.override);
        toast.success("Override added");
      } else if ("error" in result && result.error) {
        setError(result.error);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--color-accent)]/30 bg-[var(--color-accent-soft)]/30 p-4"
    >
      {error && <ErrorMessage>{error}</ErrorMessage>}

      <Input
        label="Item ID"
        value={itemId}
        onChange={(e) => setItemId(e.target.value)}
        placeholder="UUID of the catalog item"
        required
      />
      <p className="-mt-2 text-xs text-[var(--color-text-tertiary)]">
        The canonical item UUID from the SyncUp catalog. A name-based picker will
        arrive once the backend exposes item lookup for overrides.
      </p>

      <div className="space-y-2">
        <label className="block text-[15px] font-medium text-[var(--color-text-primary)]">
          Boost multiplier: <span className="text-[var(--color-accent)]">×{boost.toFixed(1)}</span>
        </label>
        <input
          type="range"
          min={BOOST_MIN}
          max={BOOST_MAX}
          step={BOOST_STEP}
          value={boost}
          onChange={(e) => setBoost(Number(e.target.value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--color-border)] accent-[var(--color-accent)]"
        />
        <div className="flex justify-between text-[11px] text-[var(--color-text-tertiary)]">
          <span>×{BOOST_MIN.toFixed(1)} (dampen)</span>
          <span>×1.0 (neutral)</span>
          <span>×{BOOST_MAX.toFixed(0)} (boost)</span>
        </div>
      </div>

      <Input
        label="Note (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Why this boost?"
        maxLength={500}
      />

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          size="md"
          onClick={onCancel}
          disabled={pending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={pending} className="relative">
          <span className={pending ? "invisible" : undefined}>Add override</span>
          {pending && <Loader2 className="absolute h-4 w-4 animate-spin" />}
        </Button>
      </div>
    </form>
  );
}
