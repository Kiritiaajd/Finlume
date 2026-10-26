import { useColorScheme } from "react-native";

const light = {
  background: "#F6F7F9",
  surface: "#FFFFFF",
  border: "#E2E5EA",
  text: "#111827",
  muted: "#5B6472",
  primary: "#0F766E",
  success: "#15803D",
  warning: "#B45309",
  danger: "#B91C1C",
};

const dark: typeof light = {
  background: "#0B0F14",
  surface: "#141A21",
  border: "#262F3A",
  text: "#E5E9EF",
  muted: "#9AA4B2",
  primary: "#2DD4BF",
  success: "#4ADE80",
  warning: "#FBBF24",
  danger: "#F87171",
};

export type Palette = typeof light;

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? dark : light;
}
