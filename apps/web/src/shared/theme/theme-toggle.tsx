"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "dark" | "light";

const STORAGE_KEY = "rezumi-theme";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    // Intentional post-hydration read: theme starts null so SSR and client
    // markup match, then syncs to the real DOM class once mounted.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(
      document.documentElement.classList.contains("dark") ? "dark" : "light",
    );
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore storage failures (private mode); the class change still applies.
    }
    setTheme(next);
  }

  const isDark = theme === "dark";

  return (
    <button
      aria-label={
        theme === null
          ? "Toggle color theme"
          : isDark
            ? "Switch to light theme"
            : "Switch to dark theme"
      }
      className="grid size-10 place-items-center rounded-[var(--radius-control)] border border-line text-muted-strong transition-colors hover:bg-surface-subtle hover:text-foreground"
      onClick={toggle}
      type="button"
    >
      {/* Render a stable icon until mounted so SSR and client markup match. */}
      <Sun
        aria-hidden="true"
        className={theme === "dark" ? "size-[1.15rem]" : "hidden"}
      />
      <Moon
        aria-hidden="true"
        className={theme === "dark" ? "hidden" : "size-[1.15rem]"}
      />
    </button>
  );
}
