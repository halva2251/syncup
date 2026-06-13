"use client";

import {
  Fragment,
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
  type ReactNode,
} from "react";
import { ChevronDown, ChevronRight, Search, X } from "lucide-react";

export interface AccordionSelectSection<T> {
  id: string;
  label: string;
  items: T[];
}

export interface AccordionSelectProps<T> {
  name: string;
  label?: string;
  sections: AccordionSelectSection<T>[];
  selected: T[];
  onChange: (selected: T[]) => void;
  getKey: (item: T) => string;
  getLabel: (item: T) => string;
  getSectionKeys?: (item: T) => string[];
  renderChip?: (item: T, onRemove: () => void) => ReactNode;
  renderOption?: (item: T) => ReactNode;
  placeholder?: string;
  searchEnabled?: boolean;
  searchPlaceholder?: string;
  multiple?: boolean;
  grouped?: boolean;
  max?: number;
  emptyMessage?: string;
  noSearchResultsMessage?: string;
}

export function AccordionSelect<T>({
  name,
  label,
  sections,
  selected,
  onChange,
  getKey,
  getLabel,
  getSectionKeys,
  renderChip,
  renderOption,
  placeholder = "Select...",
  searchEnabled = false,
  searchPlaceholder = "Search...",
  multiple = true,
  grouped = true,
  max,
  emptyMessage = "No items available",
  noSearchResultsMessage = "No items found",
}: AccordionSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [closedSections, setClosedSections] = useState<Set<string>>(new Set());

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedKeys = useMemo(
    () => new Set(selected.map(getKey)),
    [selected, getKey],
  );

  const query = search.trim().toLowerCase();
  const isSearching = query.length > 0;

  const filterItem = useCallback(
    (item: T) => {
      if (!isSearching) return true;
      const labelText = getLabel(item).toLowerCase();
      const keyText = getKey(item).toLowerCase();
      const sectionKeys = getSectionKeys
        ? getSectionKeys(item).join(" ").toLowerCase()
        : "";
      return (
        labelText.includes(query) ||
        keyText.includes(query) ||
        sectionKeys.includes(query)
      );
    },
    [isSearching, query, getLabel, getKey, getSectionKeys],
  );

  const filteredSections = useMemo(() => {
    if (!searchEnabled || !isSearching) return sections;
    return sections
      .map((section) => ({
        ...section,
        items: section.items.filter(filterItem),
      }))
      .filter((section) => section.items.length > 0);
  }, [sections, searchEnabled, isSearching, filterItem]);

  const filteredFlatItems = useMemo(() => {
    return sections.flatMap((section) => section.items).filter(filterItem);
  }, [sections, filterItem]);

  const openSections = useMemo(() => {
    if (isSearching) {
      return new Set(filteredSections.map((s) => s.id));
    }
    const next = new Set(sections.map((s) => s.id));
    closedSections.forEach((id) => next.delete(id));
    return next;
  }, [isSearching, filteredSections, sections, closedSections]);

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
    if (isOpen && searchEnabled) {
      inputRef.current?.focus();
    }
  }, [isOpen, searchEnabled]);

  const toggleSection = (sectionId: string) => {
    setClosedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

  const toggleItem = (item: T) => {
    const key = getKey(item);
    if (selectedKeys.has(key)) {
      onChange(multiple ? selected.filter((s) => getKey(s) !== key) : []);
    } else if (!multiple) {
      onChange([item]);
      setIsOpen(false);
      if (isSearching) {
        setSearch("");
      }
    } else if (max === undefined || selected.length < max) {
      onChange([...selected, item]);
      if (isSearching) {
        setSearch("");
      }
    }
  };

  const removeItem = (item: T) => {
    const key = getKey(item);
    onChange(selected.filter((s) => getKey(s) !== key));
  };

  const renderItem = (item: T) => {
    const key = getKey(item);
    const isSelected = selectedKeys.has(key);
    const isDisabled =
      !isSelected && max !== undefined && selected.length >= max;
    return (
      <button
        key={key}
        type="button"
        onClick={() => toggleItem(item)}
        disabled={isDisabled}
        className={[
          "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
          "hover:bg-[var(--color-bg-page)] disabled:cursor-not-allowed disabled:opacity-50",
          isSelected
            ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
            : "text-[var(--color-text-primary)]",
        ].join(" ")}
      >
        {renderOption ? renderOption(item) : getLabel(item)}
      </button>
    );
  };

  const defaultChip = (item: T, onRemove: () => void) => (
    <span
      key={getKey(item)}
      className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-sm font-medium text-[var(--color-accent)]"
    >
      {renderOption ? renderOption(item) : getLabel(item)}
      <span
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="cursor-pointer rounded-sm hover:bg-[var(--color-accent)]/10"
        aria-label={`Remove ${getLabel(item)}`}
        role="button"
      >
        <X className="h-3.5 w-3.5" />
      </span>
    </span>
  );

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]">
          {label}
        </label>
      )}

      <input
        type="hidden"
        name={name}
        value={JSON.stringify(selected.map(getKey))}
      />

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
              {placeholder}
            </span>
          ) : (
            selected.map((item) =>
              renderChip ? (
                <Fragment key={getKey(item)}>
                  {renderChip(item, () => removeItem(item))}
                </Fragment>
              ) : (
                defaultChip(item, () => removeItem(item))
              ),
            )
          )}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1.5 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] p-2 shadow-lg">
          {searchEnabled && (
            <div className="relative mb-2">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg-page)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
          )}

          <div className="max-h-60 overflow-auto">
            {grouped
              ? filteredSections.length === 0 && (
                  <p className="px-3 py-2 text-sm text-[var(--color-text-tertiary)]">
                    {isSearching ? noSearchResultsMessage : emptyMessage}
                  </p>
                )
              : filteredFlatItems.length === 0 && (
                  <p className="px-3 py-2 text-sm text-[var(--color-text-tertiary)]">
                    {isSearching ? noSearchResultsMessage : emptyMessage}
                  </p>
                )}

            {grouped ? (
              filteredSections.map((section) => {
                const isExpanded = openSections.has(section.id);
                return (
                  <div
                    key={section.id}
                    className="border-b border-[var(--color-border-subtle)] last:border-b-0"
                  >
                    <button
                      type="button"
                      onClick={() => toggleSection(section.id)}
                      className="flex w-full items-center justify-between px-2 py-2 text-left text-sm font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-bg-page)]"
                    >
                      <span>
                        {section.label}{" "}
                        <span className="text-[var(--color-text-tertiary)]">
                          ({section.items.length})
                        </span>
                      </span>
                      <ChevronRight
                        className={`h-4 w-4 text-[var(--color-text-tertiary)] transition-transform ${isExpanded ? "rotate-90" : ""}`}
                      />
                    </button>
                    {isExpanded && (
                      <div className="pb-2">
                        {section.items.map((item) => renderItem(item))}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="py-1">
                {filteredFlatItems.map((item) => renderItem(item))}
              </div>
            )}
          </div>

          {max !== undefined && (
            <p className="mt-2 border-t border-[var(--color-border-subtle)] px-2 pt-2 text-xs text-[var(--color-text-tertiary)]">
              {selected.length} of {max} selected
            </p>
          )}
        </div>
      )}
    </div>
  );
}
