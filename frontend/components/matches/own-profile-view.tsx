"use client";

import { Eye, Pencil } from "lucide-react";
import { useState, type ReactNode } from "react";

interface OwnProfileViewProps {
  preview: ReactNode;
  edit: ReactNode;
  initialMode?: "preview" | "edit";
}

/** Switches the signed-in profile between its public preview and edit surfaces. */
export function OwnProfileView({
  preview,
  edit,
  initialMode = "preview",
}: OwnProfileViewProps) {
  const [mode, setMode] = useState<"preview" | "edit">(initialMode);
  const isEditing = mode === "edit";

  return (
    <div>
      <button
        type="button"
        onClick={() => setMode(isEditing ? "preview" : "edit")}
        className="fixed bottom-[calc(5rem+env(safe-area-inset-bottom))] left-1/2 z-40 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-2 text-xs font-medium text-[var(--color-text-secondary)] shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-[var(--color-bg-page)] hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] sm:bottom-[calc(6rem+env(safe-area-inset-bottom))]"
        aria-label={isEditing ? "Preview your profile" : "Edit your profile"}
      >
        {isEditing ? <Eye className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
        <span>{isEditing ? "Preview" : "Edit"}</span>
      </button>

      {isEditing ? edit : preview}
    </div>
  );
}
