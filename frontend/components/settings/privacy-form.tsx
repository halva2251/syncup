"use client";

import { useState, useTransition } from "react";
import { toast } from "@/components/ui/toast";
import { updateMatchableAction } from "@/lib/actions/settings-actions";
import { cn } from "@/lib/utils/cn";

interface PrivacyFormProps {
  initialIsMatchable: boolean;
}

export function PrivacyForm({ initialIsMatchable }: PrivacyFormProps) {
  const [isMatchable, setIsMatchable] = useState(initialIsMatchable);
  const [pending, startTransition] = useTransition();

  function handleToggle(next: boolean) {
    if (pending || next === isMatchable) return;
    setIsMatchable(next);
    startTransition(async () => {
      const result = await updateMatchableAction(next);
      if ("error" in result && result.error) {
        setIsMatchable(!next); // rollback
        toast.error(result.error);
        return;
      }
      toast.success(
        next ? "You're now visible in match feeds" : "You're hidden from matches",
      );
    });
  }

  return (
    <div className="divide-y divide-[var(--color-border-subtle)]">
      <div className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="max-w-md space-y-1">
          <h3 className="text-[15px] font-medium text-[var(--color-text-primary)]">
            Discoverable matching
          </h3>
          <p className="text-[13px] text-[var(--color-text-secondary)]">
            When on, you appear in other people&apos;s match feeds and we compute
            matches for you. Turn off any time to pause.
          </p>
        </div>
        <Toggle
          checked={isMatchable}
          disabled={pending}
          onChange={handleToggle}
          label="Toggle discoverable matching"
        />
      </div>
    </div>
  );
}

interface ToggleProps {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  label: string;
}

function Toggle({ checked, disabled, onChange, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-card)] disabled:opacity-60",
        checked
          ? "bg-[var(--color-accent)]"
          : "bg-[var(--color-border)]",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
