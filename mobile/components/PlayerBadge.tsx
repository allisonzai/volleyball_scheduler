import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface Props {
  displayName: string;
  signupNumber?: number | null;
  highlight?: boolean;
}

export default function PlayerBadge({ displayName, signupNumber, highlight }: Props) {
  return (
    <View style={[styles.container, highlight && styles.highlight]}>
      {signupNumber != null && (
        <Text style={styles.number}>#{signupNumber}</Text>
      )}
      <Text style={[styles.name, highlight && styles.highlightText]}>{displayName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    backgroundColor: "#fff",
    marginBottom: 6,
  },
  highlight: {
    backgroundColor: "#fefce8",
    borderColor: "#fbbf24",
  },
  number: {
    fontSize: 11,
    color: "#9ca3af",
    fontFamily: "monospace",
    marginRight: 6,
    minWidth: 24,
    textAlign: "right",
  },
  name: {
    fontSize: 14,
    color: "#1f2937",
  },
  highlightText: {
    fontWeight: "600",
  },
});
