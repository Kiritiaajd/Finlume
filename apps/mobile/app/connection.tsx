import { ScrollView, StyleSheet, Text } from "react-native";

import { ApiStatusCard } from "../src/components/ApiStatusCard";
import { Card } from "../src/components/Card";
import { API_BASE_URL, API_VERSION_PATH, isApiConfigured } from "../src/config";
import { useHealth } from "../src/hooks/useHealth";
import { usePalette } from "../src/theme";

const STEPS = [
  "Start Django on your network interface: python manage.py runserver 0.0.0.0:8000",
  "Add your computer's LAN IP to DJANGO_ALLOWED_HOSTS in the repository's .env",
  "Set EXPO_PUBLIC_API_BASE_URL=http://<that IP>:8000 in apps/mobile/.env",
  "Restart Expo (npx expo start --clear) so the new value is bundled",
];

export default function ConnectionScreen() {
  const palette = usePalette();
  const health = useHealth();
  const mono = { color: palette.text, fontFamily: "monospace" } as const;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <ApiStatusCard {...health} onRefresh={() => void health.refresh()} />

      <Card title="API address">
        <Text style={mono}>
          {isApiConfigured ? `${API_BASE_URL}${API_VERSION_PATH}/` : "Not configured"}
        </Text>
        <Text style={{ color: palette.muted }}>
          The app uses the same versioned Django API as the web client. Only the public health
          check is used today; sign-in is not implemented yet.
        </Text>
      </Card>

      <Card title="Connect during development">
        {STEPS.map((step, index) => (
          <Text key={step} style={{ color: palette.muted }}>
            {index + 1}. {step}
          </Text>
        ))}
        <Text style={{ color: palette.muted }}>
          Use only a development server on a network you trust: traffic is plain HTTP.
        </Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 16 },
});
