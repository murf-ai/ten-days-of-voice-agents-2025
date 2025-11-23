import { cache } from 'react';
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import type { AppConfig } from '@/app-config';

export const CONFIG_ENDPOINT = process.env.NEXT_PUBLIC_APP_CONFIG_ENDPOINT;
export const SANDBOX_ID = process.env.SANDBOX_ID;

export const THEME_STORAGE_KEY = 'theme-mode';
export const THEME_MEDIA_QUERY = '(prefers-color-scheme: dark)';

export interface SandboxConfig {
  [key: string]:
    | { type: 'string'; value: string }
    | { type: 'number'; value: number }
    | { type: 'boolean'; value: boolean }
    | null;
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// https://react.dev/reference/react/cache#caveats
// > React will invalidate the cache for all memoized functions for each server request.
export const getAppConfig = cache(async (headers: Headers): Promise<AppConfig> => {
  if (CONFIG_ENDPOINT) {
    const sandboxId = SANDBOX_ID ?? headers.get('x-sandbox-id') ?? '';

    try {
      if (!sandboxId) {
        // Avoid throwing during server rendering which surfaces as a React server error.
        // Log a warning and fall back to the default config so the app can render.
        console.warn('SANDBOX_ID not set; falling back to APP_CONFIG_DEFAULTS');
        return APP_CONFIG_DEFAULTS;
      }

      // If the config endpoint is provided as a websocket URL (wss:// or ws://)
      // convert it to the equivalent http(s) URL so `fetch` can be used.
      let fetchEndpoint = CONFIG_ENDPOINT;
      if (typeof fetchEndpoint === 'string') {
        if (fetchEndpoint.startsWith('wss://')) {
          fetchEndpoint = fetchEndpoint.replace(/^wss:\/\//, 'https://');
        } else if (fetchEndpoint.startsWith('ws://')) {
          fetchEndpoint = fetchEndpoint.replace(/^ws:\/\//, 'http://');
        }
      }

      const response = await fetch(fetchEndpoint, {
        cache: 'no-store',
        headers: { 'X-Sandbox-ID': sandboxId },
      });

      if (response.ok) {
        // Parse response safely. Some endpoints may return a plain text "OK"
        // or other non-JSON responses; avoid throwing from JSON.parse.
        let remoteConfig: SandboxConfig | null = null;

        const contentType = response.headers.get('content-type') ?? '';

        if (contentType.includes('application/json')) {
          try {
            // expected happy path
            remoteConfig = (await response.json()) as SandboxConfig;
          } catch (err) {
            console.error('ERROR: failed to parse JSON from config endpoint', err);
          }
        } else {
          // Attempt to parse text body if it's JSON-shaped, otherwise log and skip.
          try {
            const text = await response.text();
            remoteConfig = JSON.parse(text) as SandboxConfig;
          } catch (err) {
            console.warn('CONFIG_ENDPOINT returned non-JSON response; falling back to defaults');
          }
        }

        if (remoteConfig) {
          const config: AppConfig = { ...APP_CONFIG_DEFAULTS, sandboxId };

          for (const [key, entry] of Object.entries(remoteConfig)) {
            if (entry === null) continue;
            // Only include app config entries that are declared in defaults and, if set,
            // share the same primitive type as the default value.
            if (
              (key in APP_CONFIG_DEFAULTS &&
                APP_CONFIG_DEFAULTS[key as keyof AppConfig] === undefined) ||
              (typeof config[key as keyof AppConfig] === entry.type &&
                typeof config[key as keyof AppConfig] === typeof entry.value)
            ) {
              // @ts-expect-error I'm not sure quite how to appease TypeScript, but we've thoroughly checked types above
              config[key as keyof AppConfig] = entry.value as AppConfig[keyof AppConfig];
            }
          }

          return config;
        } else {
          console.warn('Using APP_CONFIG_DEFAULTS due to empty or invalid config response');
        }
      } else {
        console.error(
          `ERROR: querying config endpoint failed with status ${response.status}: ${response.statusText}`
        );
      }
    } catch (error) {
      console.error('ERROR: getAppConfig() - lib/utils.ts', error);
    }
  }

  return APP_CONFIG_DEFAULTS;
});

// check provided accent colors against defaults
// apply styles if they differ (or in development mode)
// generate a hover color for the accent color by mixing it with 20% black
export function getStyles(appConfig: AppConfig) {
  const { accent, accentDark } = appConfig;

  return [
    accent
      ? `:root { --primary: ${accent}; --primary-hover: color-mix(in srgb, ${accent} 80%, #000); }`
      : '',
    accentDark
      ? `.dark { --primary: ${accentDark}; --primary-hover: color-mix(in srgb, ${accentDark} 80%, #000); }`
      : '',
  ]
    .filter(Boolean)
    .join('\n');
}
