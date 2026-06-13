"use client";

import { useMemo } from "react";
import {
  SUPPORTED_LANGUAGES,
  MAX_LANGUAGES,
  getLanguageName,
  getLanguageFlag,
  type Language,
} from "@/lib/constants/languages";
import { AccordionSelect } from "@/components/ui/accordion-select";
import { X } from "lucide-react";

interface LanguageSelectProps {
  name: string;
  label?: string;
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  max?: number;
}

function Flag({ code, className }: { code: string; className?: string }) {
  const country = getLanguageFlag(code);
  if (!country) return null;
  return (
    <span
      className={["fi", `fi-${country}`, className].filter(Boolean).join(" ")}
    />
  );
}

export function LanguageSelect({
  name,
  label,
  selected,
  onChange,
  placeholder = "Select languages...",
  max = MAX_LANGUAGES,
}: LanguageSelectProps) {
  const selectedLanguages = useMemo(
    () => selected.map((code) => ({ code, name: getLanguageName(code) ?? code })),
    [selected]
  );

  const sections = useMemo(() => {
    const grouped = new Map<string, Language[]>();
    for (const lang of SUPPORTED_LANGUAGES) {
      const letter = lang.name.charAt(0).toUpperCase();
      if (!grouped.has(letter)) {
        grouped.set(letter, []);
      }
      grouped.get(letter)!.push(lang);
    }
    return Array.from(grouped.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([letter, items]) => ({
        id: letter,
        label: letter,
        items,
      }));
  }, []);

  const handleChange = (items: Language[]) => {
    onChange(items.map((item) => item.code));
  };

  return (
    <AccordionSelect
      name={name}
      label={label}
      sections={sections}
      selected={selectedLanguages}
      onChange={handleChange}
      getKey={(lang) => lang.code}
      getLabel={(lang) => lang.name}
      searchEnabled
      searchPlaceholder="Search languages..."
      placeholder={placeholder}
      max={max}
      emptyMessage="No languages available"
      noSearchResultsMessage="No languages found"
      renderChip={(lang, onRemove) => (
        <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-sm font-medium text-[var(--color-accent)]">
          <Flag code={lang.code} className="h-3 w-4 rounded-sm" />
          {lang.name}
          <span
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="cursor-pointer rounded-sm hover:bg-[var(--color-accent)]/10"
            aria-label={`Remove ${lang.name}`}
            role="button"
          >
            <X className="h-3.5 w-3.5" />
          </span>
        </span>
      )}
      renderOption={(lang) => (
        <>
          <Flag code={lang.code} className="h-3.5 w-5 rounded-sm" />
          <span>
            {lang.name}{" "}
            <span className="text-[var(--color-text-tertiary)]">
              ({lang.code})
            </span>
          </span>
        </>
      )}
    />
  );
}
