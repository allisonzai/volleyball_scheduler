import { useEffect, useState } from "react";
import { registerForPushNotifications } from "../services/notifications";

export function usePushToken(playerId: number | null) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId) return;
    registerForPushNotifications(playerId)
      .then(setToken)
      .catch((e) => console.warn("Push registration failed:", e));
  }, [playerId]);

  return token;
}
