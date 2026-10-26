import Ionicons from "@expo/vector-icons/Ionicons";
import { Tabs } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { usePalette } from "../src/theme";

export default function RootLayout() {
  const palette = usePalette();

  return (
    <>
      <StatusBar style="auto" />
      <Tabs
        screenOptions={{
          tabBarActiveTintColor: palette.primary,
          tabBarInactiveTintColor: palette.muted,
          tabBarStyle: { backgroundColor: palette.surface, borderTopColor: palette.border },
          headerStyle: { backgroundColor: palette.surface },
          headerTintColor: palette.text,
          sceneStyle: { backgroundColor: palette.background },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: "Dashboard",
            tabBarIcon: ({ focused, size }) => (
              <Ionicons
                name="grid-outline"
                color={focused ? palette.primary : palette.muted}
                size={size}
              />
            ),
          }}
        />
        <Tabs.Screen
          name="connection"
          options={{
            title: "Connection",
            tabBarIcon: ({ focused, size }) => (
              <Ionicons
                name="server-outline"
                color={focused ? palette.primary : palette.muted}
                size={size}
              />
            ),
          }}
        />
      </Tabs>
    </>
  );
}
