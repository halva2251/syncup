"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import {
  SUPPORTED_LANGUAGES,
  MAX_LANGUAGES,
  getLanguageName,
  getLanguageFlag,
} from "@/lib/constants/languages";
import { ChevronDown, X, Search } from "lucide-react";

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
  placeholder = "Search languages...",
  max = MAX_LANGUAGES,
}: LanguageSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const available = useMemo(() => {
    const query = search.trim().toLowerCase();
    return SUPPORTED_LANGUAGES.filter(
      (lang) =>
        !selected.includes(lang.code) &&
        (lang.name.toLowerCase().includes(query) ||
          lang.code.toLowerCase().includes(query))
    );
  }, [search, selected]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  const toggleLanguage = (code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code));
    } else if (selected.length < max) {
      onChange([...selected, code]);
      setSearch("");
    }
  };

  const removeLanguage = (code: string) => {
    onChange(selected.filter((c) => c !== code));
  };

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]">
          {label}
        </label>
      )}

      <input type="hidden" name={name} value={JSON.stringify(selected)} />

      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={[
          "flex min-h-[42px] w-full items-center justify-between rounded-lg border bg-[var(--color-bg-card)] px-3.5 py-2 text-left text-[15px] transition-colors",
          "border-[var(--color-border)] hover:border-[var(--color-accent)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-[3px] focus:ring-[var(--color-accent-soft)]",
        ].join(" ")}
      >
        <span className="flex flex-wrap gap-1.5">
          {selected.length === 0 ? (
            <span className="text-[var(--color-text-tertiary)]">
              Select languages...
            </span>
          ) : (
            selected.map((code) => (
              <span
                key={code}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-sm font-medium text-[var(--color-accent)]"
              >
                <Flag code={code} className="h-3 w-4 rounded-sm" />
                {getLanguageName(code) ?? code}
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    removeLanguage(code);
                  }}
                  className="cursor-pointer rounded-sm hover:bg-[var(--color-accent)]/10"
                >
                  <X className="h-3.5 w-3.5" />
                </span>
              </span>
            ))
          )}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-2 shadow-lg">
          <div className="relative mb-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={placeholder}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg-page)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>

          <div className="max-h-60 overflow-auto">
            {available.length === 0 ? (
              <p className="px-3 py-2 text-sm text-[var(--color-text-tertiary)]">
                No languages found
              </p>
            ) : (
              available.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => toggleLanguage(lang.code)}
                  disabled={selected.length >= max}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-bg-page)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Flag code={lang.code} className="h-3.5 w-5 rounded-sm" />
                  <span>
                    {lang.name}{" "}
                    <span className="text-[var(--color-text-tertiary)]">
                      ({lang.code})
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>

          <p className="mt-2 border-t border-[var(--color-border-subtle)] px-2 pt-2 text-xs text-[var(--color-text-tertiary)]">
            {selected.length} of {max} selected
          </p>
        </div>
      )}
    </div>
  );
}
