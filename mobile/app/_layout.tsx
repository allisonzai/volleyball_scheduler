import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#fff" },
          headerShadowVisible: false,
          headerTitleStyle: { fontWeight: "700" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "Volleyball Scheduler" }} />
        <Stack.Screen name="register" options={{ title: "Register" }} />
        <Stack.Screen name="history" options={{ title: "Past Games" }} />
      </Stack>
    </>
  );
}
