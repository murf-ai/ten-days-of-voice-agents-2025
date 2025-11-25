'use client';

import { useEffect, useState } from 'react';
import { MonitorIcon, MoonIcon, SunIcon } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

const THEME_STORAGE_KEY = 'theme-mode';

type ThemeMode = 'dark' | 'light' | 'system';

function getSystemTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme: ThemeMode) {
  if (typeof window === 'undefined') return;

  const doc = document.documentElement;
  doc.classList.remove('dark', 'light');

  const actualTheme = theme === 'system' ? getSystemTheme() : theme;
  doc.classList.add(actualTheme);

  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const [theme, setTheme] = useState<ThemeMode>('system');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    // Get stored theme or default to system
    const storedTheme = (localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode) || 'system';
    setTheme(storedTheme);
    applyTheme(storedTheme);

    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (theme === 'system') {
        applyTheme('system');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  function handleThemeChange(newTheme: ThemeMode) {
    setTheme(newTheme);
    applyTheme(newTheme);
  }

  // Don't render until mounted to avoid hydration issues
  if (!mounted) {
    return null;
  }

  return (
    <div
      className={cn(
        'text-foreground bg-background flex w-full flex-row justify-end divide-x overflow-hidden rounded-full border',
        className
      )}
    >
      <span className="sr-only">Color scheme toggle</span>
      <button
        type="button"
        onClick={() => handleThemeChange('dark')}
        className="cursor-pointer p-1 pl-1.5"
        aria-label="Enable dark mode"
      >
        <MoonIcon size={16} weight="bold" className={cn(theme !== 'dark' && 'opacity-25')} />
      </button>
      <button
        type="button"
        onClick={() => handleThemeChange('light')}
        className="cursor-pointer px-1.5 py-1"
        aria-label="Enable light mode"
      >
        <SunIcon size={16} weight="bold" className={cn(theme !== 'light' && 'opacity-25')} />
      </button>
      <button
        type="button"
        onClick={() => handleThemeChange('system')}
        className="cursor-pointer p-1 pr-1.5"
        aria-label="Use system theme"
      >
        <MonitorIcon size={16} weight="bold" className={cn(theme !== 'system' && 'opacity-25')} />
      </button>
    </div>
  );
}
