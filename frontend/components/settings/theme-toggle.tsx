"use client";

import { useState } from "react";
import { Moon, Sun } from "lucide-react";

const THEME_STORAGE_KEY = "syncup-theme";

/** Persisted light/dark switch for the document-level theme tokens. */
export function ThemeToggle() {
  const [isDark, setIsDark] = useState(
    () =>
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("dark"),
  );

  function toggleTheme() {
    const nextIsDark = !isDark;
    document.documentElement.classList.toggle("dark", nextIsDark);
    localStorage.setItem(THEME_STORAGE_KEY, nextIsDark ? "dark" : "light");
    setIsDark(nextIsDark);
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      suppressHydrationWarning
      onClick={toggleTheme}
      className="inline-flex h-10 w-[4.75rem] items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-page)] p-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-card)]"
    >
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-transform ${
          isDark ? "translate-x-8" : "translate-x-0"
        }`}
      >
        {isDark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      </span>
    </button>
  );
}
