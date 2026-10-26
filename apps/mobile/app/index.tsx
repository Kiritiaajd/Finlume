import { ScrollView, StyleSheet, Text } from "react-native";

import { ApiStatusCard } from "../src/components/ApiStatusCard";
import { Card } from "../src/components/Card";
import { useHealth } from "../src/hooks/useHealth";
import { usePalette } from "../src/theme";

const UPCOMING = [
  "Workspaces and sign-in",
  "Financial statements and CSV import",
  "Saved analyses with ratios and validation warnings",
  "Reports",
];

export default function DashboardScreen() {
  const palette = usePalette();
  const health = useHealth();

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text accessibilityRole="header" style={[styles.heading, { color: palette.text }]}>
        Welcome to Finlume
      </Text>
      <Text style={{ color: palette.muted }}>
        Open-source financial intelligence: verifiable calculations, explained clearly.
      </Text>

      <ApiStatusCard {...health} onRefresh={() => void health.refresh()} />

      <Card title="No financial data yet">
        <Text style={{ color: palette.muted }}>
          Your statements, analyses and reports will appear here. The backend does not offer
          those features yet, and this app never shows sample figures as if they were yours.
        </Text>
      </Card>

      <Card title="Coming with the MVP">
        {UPCOMING.map((item) => (
          <Text key={item} style={{ color: palette.muted }}>
            {"•"} {item}
          </Text>
        ))}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 16 },
  heading: { fontSize: 24, fontWeight: "700" },
});
