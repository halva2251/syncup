"use client";

import { useActionState, useOptimistic, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Autocomplete } from "@/components/ui/autocomplete";
import { ErrorMessage } from "@/components/ui/error-message";
import { AccordionSelect } from "@/components/ui/accordion-select";
import { OnboardingStep } from "@/components/onboarding/onboarding-step";
import { Loader2, Heart, X } from "lucide-react";
import {
  createObsessionAction,
  deleteObsessionAction,
} from "@/lib/actions/obsession-actions";
import type { ManualObsession } from "@/types/api";

interface CategoryItem {
  value: string;
  label: string;
}

const CATEGORY_SECTIONS = [
  {
    id: "media",
    label: "Media & Entertainment",
    items: [
      { value: "game", label: "Game" },
      { value: "music", label: "Music" },
      { value: "film", label: "Film" },
      { value: "book", label: "Book" },
      { value: "show", label: "Show" },
      { value: "anime", label: "Anime" },
      { value: "manga", label: "Manga" },
    ],
  },
  {
    id: "community",
    label: "Community",
    items: [{ value: "community", label: "Community" }],
  },
  {
    id: "other",
    label: "Other",
    items: [{ value: "other", label: "Other" }],
  },
];

interface ObsessionsStepFormProps {
  initialObsessions: ManualObsession[];
}

export function ObsessionsStepForm({
  initialObsessions,
}: ObsessionsStepFormProps) {
  const [obsessions, setObsessions] = useState(initialObsessions);
  const [optimisticObsessions, setOptimisticObsessions] =
    useOptimistic(obsessions);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<CategoryItem[]>([]);
  const [autocompleteKey, setAutocompleteKey] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);

  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string } | null, formData: FormData) => {
      const result = await createObsessionAction(formData);
      if ("error" in result && result.error) {
        return { error: result.error };
      }
      if ("obsession" in result && result.obsession) {
        setObsessions((prev) => [result.obsession!, ...prev]);
        setSelectedCategory([]);
        setAutocompleteKey((prev) => prev + 1);
        formRef.current?.reset();
      }
      return null;
    },
    null
  );

  async function handleDelete(id: string) {
    setPendingDeleteId(id);
    setOptimisticObsessions((prev) => prev.filter((o) => o.id !== id));
    const result = await deleteObsessionAction(id);
    setPendingDeleteId(null);
    if (result.error) {
      // Rollback on error
      setObsessions((prev) => {
        const removed = initialObsessions.find((o) => o.id === id);
        return removed && !prev.some((o) => o.id === id)
          ? [...prev, removed]
          : prev;
      });
      return;
    }
    setObsessions((prev) => prev.filter((o) => o.id !== id));
  }

  const displayList = optimisticObsessions;

  return (
    <OnboardingStep
      icon={Heart}
      title="What are you obsessed with?"
      description="Add at least 3 things that define your taste — games, albums, books, shows, communities, anything."
      backHref="/onboarding/services"
      continueHref="/onboarding/taste"
    >
      <form ref={formRef} action={formAction} className="space-y-5">
        {state?.error && <ErrorMessage>{state.error}</ErrorMessage>}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="sm:w-56">
            <AccordionSelect
              name="category"
              label="Category"
              sections={CATEGORY_SECTIONS}
              selected={selectedCategory}
              onChange={setSelectedCategory}
              getKey={(c) => c.value}
              getLabel={(c) => c.label}
              multiple={false}
              grouped={false}
              placeholder="Select a category"
              emptyMessage="No categories available"
            />
          </div>

          <Autocomplete
            key={autocompleteKey}
            name="name"
            label="Name"
            placeholder="e.g. Disco Elysium"
            required
            category={selectedCategory[0]?.value ?? ""}
            className="flex-1"
          />

          <Button
            type="submit"
            disabled={pending}
            className="h-[42px] w-full sm:w-auto"
          >
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Add
          </Button>
        </div>

        <p className="text-[13px] text-[var(--color-text-tertiary)]">
          {displayList.length} added — add 3 or more, or connect a service next
          to improve matches.
        </p>
      </form>

      {displayList.length > 0 && (
        <ul className="mt-6 flex flex-wrap gap-2">
          {displayList.map((obsession) => (
            <li
              key={obsession.id}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-page)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
            >
              <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
                {obsession.category}
              </span>
              <span className="max-w-[200px] truncate">{obsession.name}</span>
              <button
                type="button"
                onClick={() => handleDelete(obsession.id)}
                disabled={pendingDeleteId === obsession.id}
                className="rounded-md p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
                aria-label={`Remove ${obsession.name}`}
              >
                {pendingDeleteId === obsession.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <X className="h-3.5 w-3.5" />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

    </OnboardingStep>
  );
}
