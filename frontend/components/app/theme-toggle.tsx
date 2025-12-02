'use client';

import { useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

// Constants
const THEME_STORAGE_KEY = 'theme-preference';
const THEME_MEDIA_QUERY = '(prefers-color-scheme: dark)';

// Minified script to prevent FOUC (Flash of Unstyled Content)
const THEME_SCRIPT = `
  (function() {
    try {
      const doc = document.documentElement;
      const localTheme = localStorage.getItem("${THEME_STORAGE_KEY}");
      const systemTheme = window.matchMedia("${THEME_MEDIA_QUERY}").matches ? "dark" : "light";
      
      doc.classList.remove("light", "dark");
      
      if (localTheme === "dark" || (!localTheme && systemTheme === "dark") || (localTheme === "system" && systemTheme === "dark")) {
        doc.classList.add("dark");
      } else {
        doc.classList.add("light");
      }
    } catch (e) {}
  })();
`
  .replace(/\n/g, '')
  .replace(/\s+/g, ' ');

export type ThemeMode = 'dark' | 'light' | 'system';

export function ApplyThemeScript() {
  return (
    <script
      id="theme-script"
      dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }}
    />
  );
}

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const [theme, setTheme] = useState<ThemeMode | undefined>(undefined);

  // 1. Initialize state on mount
  useEffect(() => {
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode;
    setTheme(stored ?? 'system');
  }, []);

  // 2. Listen for system changes when mode is 'system'
  useEffect(() => {
    if (theme !== 'system') return;

    const mediaQuery = window.matchMedia(THEME_MEDIA_QUERY);
    
    const handleChange = () => {
      const doc = document.documentElement;
      doc.classList.remove('light', 'dark');
      doc.classList.add(mediaQuery.matches ? 'dark' : 'light');
    };

    // Apply immediately in case system state drifted while tab was hidden
    handleChange();

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  const updateTheme = (newTheme: ThemeMode) => {
    const doc = document.documentElement;
    
    // Save preference
    localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    setTheme(newTheme);

    // Apply classes
    doc.classList.remove('light', 'dark');

    if (newTheme === 'system') {
      const systemTheme = window.matchMedia(THEME_MEDIA_QUERY).matches ? 'dark' : 'light';
      doc.classList.add(systemTheme);
    } else {
      doc.classList.add(newTheme);
    }
  };

  // Prevent hydration mismatch by rendering a placeholder until mounted
  if (!theme) return <div className={cn("h-9 w-24 rounded-full bg-muted/20", className)} />;

  return (
    <div
      className={cn(
        'group relative flex items-center justify-center rounded-full bg-neutral-100 p-1 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800',
        className
      )}
      role="radiogroup"
      aria-label="Theme toggle"
    >
      <ThemeButton
        mode="light"
        current={theme}
        onClick={() => updateTheme('light')}
        icon={<Sun weight={theme === 'light' ? 'fill' : 'bold'} />}
        label="Light"
      />
      <ThemeButton
        mode="system"
        current={theme}
        onClick={() => updateTheme('system')}
        icon={<Monitor weight={theme === 'system' ? 'fill' : 'bold'} />}
        label="System"
      />
      <ThemeButton
        mode="dark"
        current={theme}
        onClick={() => updateTheme('dark')}
        icon={<Moon weight={theme === 'dark' ? 'fill' : 'bold'} />}
        label="Dark"
      />
    </div>
  );
}

// Sub-component for cleaner render logic
function ThemeButton({
  mode,
  current,
  onClick,
  icon,
  label
}: {
  mode: ThemeMode;
  current: ThemeMode;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  const isActive = current === mode;

  return (
    <button
      type="button"
      role="radio"
      aria-checked={isActive}
      aria-label={`Switch to ${label} theme`}
      onClick={onClick}
      className={cn(
        'relative flex h-7 w-7 items-center justify-center rounded-full text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500',
        isActive 
          ? 'bg-white text-neutral-950 shadow-sm dark:bg-neutral-800 dark:text-neutral-50 hover:bg-neutral-50 dark:hover:bg-neutral-700' 
          : 'text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50'
      )}
    >
      <span className="z-10 text-base">{icon}</span>
    </button>
  );
}