import { createContext, useContext } from "react";

import type { Preferences } from "./preferences";

export interface PreferencesContextValue {
  preferences: Preferences;
  setPreferences: (next: Preferences) => void;
  resolvedTheme: "light" | "dark";
}

export const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error("usePreferences must be used inside <PreferencesProvider>.");
  return context;
}
