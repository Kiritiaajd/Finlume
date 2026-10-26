import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import type { HealthResult } from "../api/health";
import { API_BASE_URL } from "../config";
import { type Palette, usePalette } from "../theme";
import { Card } from "./Card";

type Props = {
  result: HealthResult | null;
  checking: boolean;
  onRefresh: () => void;
};

function describe(result: HealthResult, palette: Palette) {
  switch (result.kind) {
    case "ok":
      return { label: "Connected", color: palette.success, body: `API reachable at ${API_BASE_URL}.` };
    case "degraded":
      return {
        label: "Database unavailable",
        color: palette.warning,
        body: "The API is running but cannot reach its database.",
      };
    case "not-configured":
      return {
        label: "Not configured",
        color: palette.muted,
        body: "Set EXPO_PUBLIC_API_BASE_URL to connect. See the Connection tab.",
      };
    case "unreachable":
      return {
        label: "API unavailable",
        color: palette.danger,
        body: `Could not reach ${API_BASE_URL}. Is the Django server running and reachable from this device? (${result.detail})`,
      };
    case "unexpected":
      return {
        label: "Unexpected response",
        color: palette.danger,
        body: `The server did not answer like the Finlume API (${result.detail}).`,
      };
  }
}

export function ApiStatusCard({ result, checking, onRefresh }: Props) {
  const palette = usePalette();
  const status = result ? describe(result, palette) : null;

  return (
    <Card title="Backend connection">
      {status === null ? (
        <View style={styles.row}>
          <ActivityIndicator color={palette.primary} />
          <Text style={{ color: palette.muted }}>Checking the API…</Text>
        </View>
      ) : (
        <>
          <View style={styles.row} accessibilityLiveRegion="polite">
            <View style={[styles.dot, { backgroundColor: status.color }]} />
            <Text style={[styles.label, { color: status.color }]}>{status.label}</Text>
          </View>
          <Text style={{ color: palette.muted }}>{status.body}</Text>
        </>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled: checking }}
        disabled={checking}
        onPress={onRefresh}
        style={({ pressed }) => [
          styles.button,
          { borderColor: palette.border, opacity: checking ? 0.5 : pressed ? 0.7 : 1 },
        ]}
      >
        <Text style={{ color: palette.primary, fontWeight: "600" }}>
          {checking ? "Checking…" : "Check again"}
        </Text>
      </Pressable>
    </Card>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  label: { fontWeight: "600" },
  button: {
    alignSelf: "flex-start",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 4,
  },
});
