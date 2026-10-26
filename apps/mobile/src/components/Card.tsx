import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { usePalette } from "../theme";

type CardProps = {
  title: string;
  children: ReactNode;
};

export function Card({ title, children }: CardProps) {
  const palette = usePalette();
  return (
    <View style={[styles.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
      <Text accessibilityRole="header" style={[styles.title, { color: palette.text }]}>
        {title}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 16,
    gap: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
  },
});
