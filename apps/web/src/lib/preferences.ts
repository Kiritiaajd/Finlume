import { z } from "zod";

/**
 * Display preferences, kept only in this browser (localStorage). They are a
 * convenience, not account settings: nothing here is sent to the backend.
 */
export const LOCALE_OPTIONS = {
  "en-US": "English (United States)",
  "en-GB": "English (United Kingdom)",
  "en-IN": "English (India)",
  "de-DE": "Deutsch (Deutschland)",
  "fr-FR": "Français (France)",
} as const;

export const preferencesSchema = z.object({
  locale: z.enum(["en-US", "en-GB", "en-IN", "de-DE", "fr-FR"]),
  theme: z.enum(["system", "light", "dark"]),
  ratioDisplay: z.enum(["percent", "decimal"]),
});

export type Preferences = z.infer<typeof preferencesSchema>;

export const DEFAULT_PREFERENCES: Preferences = {
  locale: "en-US",
  theme: "system",
  ratioDisplay: "percent",
};

export const PREFERENCES_STORAGE_KEY = "finlume.preferences.v1";

export function loadPreferences(): Preferences {
  try {
    const raw = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = preferencesSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES; // storage blocked or corrupt: fall back to defaults
  }
}

export function savePreferences(preferences: Preferences): void {
  try {
    window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Private mode or blocked storage: preferences last for this session only.
  }
}
