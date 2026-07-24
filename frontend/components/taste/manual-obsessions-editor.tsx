"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import { ObsessionsStepForm } from "@/components/onboarding/obsessions-step-form";
import type { ManualObsession } from "@/types/api";

interface ManualObsessionsEditorProps {
  initialObsessions: ManualObsession[];
}

/** Inline live editor for the signed-in user's manual taste entries. */
export function ManualObsessionsEditor({
  initialObsessions,
}: ManualObsessionsEditorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [obsessions, setObsessions] = useState(initialObsessions);

  if (!isOpen) {
    return (
      <ul className="flex flex-wrap gap-1.5">
        {obsessions.map((obsession) => (
          <li
            key={obsession.id}
            className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] px-2.5 py-1 text-sm text-[var(--color-text-primary)]"
          >
            {obsession.name}
          </li>
        ))}
        <li>
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-accent-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            aria-label="Add an obsession"
            title="Add an obsession"
          >
            <Plus className="h-4 w-4" />
          </button>
        </li>
      </ul>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-page)] p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="font-medium text-[var(--color-text-primary)]">Obsessions</h3>
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="rounded-md p-1 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
          aria-label="Close obsession editor"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <ObsessionsStepForm
        initialObsessions={obsessions}
        onObsessionsChange={setObsessions}
        embedded
      />
    </div>
  );
}
