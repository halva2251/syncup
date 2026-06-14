"use client";

import {
  Fragment,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { ChevronDown, ChevronRight, Search, X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

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
  const [activeIndex, setActiveIndex] = useState(-1);

  const id = useId();
  const listboxId = `${id}-listbox`;
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  const visibleItems = useMemo(() => {
    return grouped
      ? filteredSections.flatMap((section) => section.items)
      : filteredFlatItems;
  }, [grouped, filteredSections, filteredFlatItems]);

  const openSections = useMemo(() => {
    if (isSearching) {
      return new Set(filteredSections.map((s) => s.id));
    }
    const next = new Set(sections.map((s) => s.id));
    closedSections.forEach((id) => next.delete(id));
    return next;
  }, [isSearching, filteredSections, sections, closedSections]);

  const optionIndexByKey = useMemo(() => {
    const map = new Map<string, number>();
    visibleItems.forEach((item, index) => map.set(getKey(item), index));
    return map;
  }, [visibleItems, getKey]);

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

  const safeActiveIndex = Math.min(activeIndex, visibleItems.length - 1);

  useEffect(() => {
    if (safeActiveIndex >= 0 && safeActiveIndex < visibleItems.length) {
      const element = document.getElementById(
        `${listboxId}-option-${safeActiveIndex}`,
      );
      element?.scrollIntoView({ block: "nearest" });
    }
  }, [safeActiveIndex, listboxId, visibleItems.length]);

  const openDropdown = () => {
    setSearch("");
    setActiveIndex(visibleItems.length > 0 ? 0 : -1);
    setIsOpen(true);
    if (searchEnabled) {
      // Defer focus until after the dropdown renders.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  };

  const closeDropdown = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

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

  const toggleItem = useCallback(
    (item: T) => {
      const key = getKey(item);
      if (selectedKeys.has(key)) {
        onChange(multiple ? selected.filter((s) => getKey(s) !== key) : []);
      } else if (!multiple) {
        onChange([item]);
        setIsOpen(false);
        setSearch("");
      } else if (max === undefined || selected.length < max) {
        onChange([...selected, item]);
        setSearch("");
      }
    },
    [selected, selectedKeys, getKey, onChange, multiple, max],
  );

  const removeItem = useCallback(
    (item: T) => {
      const key = getKey(item);
      onChange(selected.filter((s) => getKey(s) !== key));
    },
    [selected, getKey, onChange],
  );

  const handleListKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (!isOpen) return;

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setActiveIndex((prev) =>
            prev < visibleItems.length - 1 ? prev + 1 : 0,
          );
          break;
        case "ArrowUp":
          event.preventDefault();
          setActiveIndex((prev) =>
            prev > 0 ? prev - 1 : visibleItems.length - 1,
          );
          break;
        case "Home":
          event.preventDefault();
          setActiveIndex(0);
          break;
        case "End":
          event.preventDefault();
          setActiveIndex(visibleItems.length - 1);
          break;
        case "Enter":
          event.preventDefault();
          if (safeActiveIndex >= 0 && safeActiveIndex < visibleItems.length) {
            toggleItem(visibleItems[safeActiveIndex]);
          }
          break;
        case "Escape":
          event.preventDefault();
          closeDropdown();
          break;
      }
    },
    [isOpen, visibleItems, safeActiveIndex, toggleItem],
  );

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
      }
    }
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (visibleItems.length > 0) {
        setActiveIndex(0);
        document.getElementById(`${listboxId}-option-0`)?.focus();
      }
    } else if (event.key === "Escape") {
      closeDropdown();
    }
  };

  const renderItem = (item: T, index: number) => {
    const key = getKey(item);
    const isSelected = selectedKeys.has(key);
    const isDisabled = !isSelected && max !== undefined && selected.length >= max;
    const isActive = index === safeActiveIndex;
    const optionId = `${listboxId}-option-${index}`;

    return (
      <div
        key={key}
        id={optionId}
        role="option"
        aria-selected={isSelected}
        tabIndex={-1}
        onClick={() => toggleItem(item)}
        onMouseEnter={() => setActiveIndex(index)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggleItem(item);
          } else {
            handleListKeyDown(e);
          }
        }}
        aria-disabled={isDisabled}
        className={cn(
          "flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]",
          isActive && !isSelected && "bg-[var(--color-bg-page)]",
          isSelected
            ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
            : "text-[var(--color-text-primary)]",
          isDisabled && "cursor-not-allowed opacity-50",
        )}
      >
        {renderOption ? renderOption(item) : getLabel(item)}
      </div>
    );
  };

  const defaultChip = (item: T, onRemove: () => void) => (
    <span
      key={getKey(item)}
      className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-sm font-medium text-[var(--color-accent)]"
    >
      {renderOption ? renderOption(item) : getLabel(item)}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="inline-flex cursor-pointer items-center rounded-sm hover:bg-[var(--color-accent)]/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        aria-label={`Remove ${getLabel(item)}`}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </span>
  );

  const triggerContent =
    selected.length === 0 ? (
      <span className="text-[var(--color-text-tertiary)]">{placeholder}</span>
    ) : !multiple ? (
      <span className="inline-flex items-center gap-2 text-[var(--color-text-primary)]">
        {renderOption ? renderOption(selected[0]) : getLabel(selected[0])}
      </span>
    ) : (
      <span>{`${selected.length} selected`}</span>
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

      {multiple && selected.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {selected.map((item) =>
            renderChip ? (
              <Fragment key={getKey(item)}>
                {renderChip(item, () => removeItem(item))}
              </Fragment>
            ) : (
              defaultChip(item, () => removeItem(item))
            ),
          )}
        </div>
      )}

      <button
        ref={triggerRef}
        type="button"
        onClick={() => (isOpen ? setIsOpen(false) : openDropdown())}
        onKeyDown={handleTriggerKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listboxId : undefined}
        className={cn(
          "flex min-h-[42px] w-full items-center justify-between rounded-lg border bg-[var(--color-bg-card)] px-3.5 py-2 text-left text-[15px] transition-colors",
          "border-[var(--color-border)] hover:border-[var(--color-accent)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-[3px] focus:ring-[var(--color-accent-soft)]",
        )}
      >
        {triggerContent}
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-[var(--color-text-tertiary)] transition-transform",
            isOpen && "rotate-180",
          )}
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
                role="combobox"
                aria-expanded={isOpen}
                aria-controls={listboxId}
                aria-activedescendant={
                  safeActiveIndex >= 0
                    ? `${listboxId}-option-${safeActiveIndex}`
                    : undefined
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder={searchPlaceholder}
                className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg-page)] py-2 pl-9 pr-3 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
          )}

          <div
            id={listboxId}
            role="listbox"
            aria-multiselectable={multiple}
            aria-label={label ?? placeholder}
            onKeyDown={handleListKeyDown}
            tabIndex={-1}
            className="max-h-60 overflow-auto focus:outline-none"
          >
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
                        className={cn(
                          "h-4 w-4 text-[var(--color-text-tertiary)] transition-transform",
                          isExpanded && "rotate-90",
                        )}
                      />
                    </button>
                    {isExpanded && (
                      <div className="pb-2">
                        {section.items.map((item) => {
                          const index = optionIndexByKey.get(getKey(item));
                          return index !== undefined
                            ? renderItem(item, index)
                            : null;
                        })}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="py-1">
                {filteredFlatItems.map((item, index) =>
                  renderItem(item, index),
                )}
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
