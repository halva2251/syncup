"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useTransition,
} from "react";
import { Loader2, Search } from "lucide-react";
import { searchItems, type SearchSuggestion } from "@/lib/api/search";

interface AutocompleteProps {
  category: string;
  name?: string;
  label?: string;
  placeholder?: string;
  required?: boolean;
  className?: string;
  defaultValue?: string;
  limit?: number;
  debounceMs?: number;
}

function str(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return null;
}

function formatSuggestionExtra(suggestion: SearchSuggestion): string | null {
  const extra = suggestion.extra;
  if (!extra) return null;

  switch (suggestion.item_type) {
    case "film":
    case "show":
    case "anime":
    case "manga":
    case "book": {
      const parts: string[] = [];
      const year = str(extra.year);
      const author = str(extra.author);
      const artist = str(extra.artist);
      if (year) parts.push(year);
      if (author) parts.push(author);
      if (artist) parts.push(artist);
      return parts.length > 0 ? parts.join(" · ") : null;
    }
    case "music": {
      const parts: string[] = [];
      const country = str(extra.country);
      const disambiguation = str(extra.disambiguation);
      if (country) parts.push(country);
      if (disambiguation) parts.push(disambiguation);
      return parts.length > 0 ? parts.join(" · ") : null;
    }
    default:
      return null;
  }
}

export function Autocomplete({
  category,
  name = "name",
  label = "Name",
  placeholder = "e.g. Disco Elysium",
  required = false,
  className,
  defaultValue = "",
  limit = 10,
  debounceMs = 300,
}: AutocompleteProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const [query, setQuery] = useState(defaultValue);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [selectedExternalId, setSelectedExternalId] = useState<string | null>(
    null,
  );
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSuggestions = useCallback(
    async (value: string) => {
      const trimmed = value.trim();
      if (!trimmed || !category) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      try {
        const items = await searchItems(category, trimmed, limit);
        setSuggestions(items);
        setIsOpen(items.length > 0);
        setHighlightedIndex(items.length > 0 ? 0 : -1);
        setError(null);
      } catch (err) {
        setSuggestions([]);
        setIsOpen(false);
        setError(err instanceof Error ? err.message : "Search failed");
      }
    },
    [category, limit]
  );

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value);
      setIsOpen(false);
      setError(null);
      setSelectedExternalId(null);
      setSelectedService(null);

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      if (!value.trim()) {
        setSuggestions([]);
        return;
      }

      debounceRef.current = setTimeout(() => {
        startTransition(() => {
          void fetchSuggestions(value);
        });
      }, debounceMs);
    },
    [fetchSuggestions, debounceMs]
  );

  const selectSuggestion = useCallback(
    (index: number) => {
      const suggestion = suggestions[index];
      if (!suggestion) return;
      setQuery(suggestion.name);
      setSelectedExternalId(suggestion.external_id);
      setSelectedService(suggestion.service);
      setSuggestions([]);
      setIsOpen(false);
      setHighlightedIndex(-1);
      inputRef.current?.focus();
    },
    [suggestions]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (!isOpen) return;

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setHighlightedIndex((prev) =>
            prev < suggestions.length - 1 ? prev + 1 : 0
          );
          break;
        case "ArrowUp":
          event.preventDefault();
          setHighlightedIndex((prev) =>
            prev > 0 ? prev - 1 : suggestions.length - 1
          );
          break;
        case "Enter":
          event.preventDefault();
          if (highlightedIndex >= 0) {
            selectSuggestion(highlightedIndex);
          }
          break;
        case "Escape":
          setIsOpen(false);
          setHighlightedIndex(-1);
          break;
      }
    },
    [isOpen, suggestions.length, highlightedIndex, selectSuggestion]
  );

  // Close dropdown when clicking outside.
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        inputRef.current &&
        !inputRef.current.contains(target) &&
        listRef.current &&
        !listRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll highlighted item into view.
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[highlightedIndex] as HTMLElement | undefined;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex]);

  return (
    <div className={["relative", className].filter(Boolean).join(" ")}>
      {label && (
        <label
          htmlFor={id}
          className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          name={name}
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          required={required}
          autoComplete="off"
          aria-autocomplete="list"
          aria-controls={isOpen ? `${id}-listbox` : undefined}
          aria-activedescendant={
            isOpen && highlightedIndex >= 0
              ? `${id}-option-${highlightedIndex}`
              : undefined
          }
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3.5 py-2 pl-9 text-[15px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] h-[42px] transition-colors hover:bg-[var(--color-bg-page)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-[3px] focus:ring-[var(--color-accent-soft)]"
        />
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[var(--color-text-tertiary)]">
          {isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </div>
        <input
          type="hidden"
          name={`${name}_external_id`}
          value={selectedExternalId ?? ""}
        />
        <input
          type="hidden"
          name={`${name}_service`}
          value={selectedService ?? ""}
        />
      </div>

      {error && (
        <p className="mt-1.5 text-xs text-[var(--color-danger)]">{error}</p>
      )}

      {isOpen && suggestions.length > 0 && (
        <ul
          ref={listRef}
          id={`${id}-listbox`}
          role="listbox"
          className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] py-1 shadow-sm"
        >
          {suggestions.map((suggestion, index) => {
            const extra = formatSuggestionExtra(suggestion);
            return (
              <li
                key={`${suggestion.service}-${suggestion.external_id ?? index}`}
                id={`${id}-option-${index}`}
                role="option"
                aria-selected={index === highlightedIndex}
                onMouseEnter={() => setHighlightedIndex(index)}
                onClick={() => selectSuggestion(index)}
                className={[
                  "cursor-pointer px-3.5 py-2 text-[15px]",
                  index === highlightedIndex
                    ? "bg-[var(--color-accent-soft)]"
                    : "",
                ].join(" ")}
              >
                <div className="text-[var(--color-text-primary)]">
                  {suggestion.name}
                </div>
                {extra && (
                  <div className="text-[13px] text-[var(--color-text-secondary)]">
                    {extra}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
