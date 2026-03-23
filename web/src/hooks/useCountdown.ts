import { useState, useEffect, useRef } from "react";

export function useCountdown(
  notifiedAt: string | null,
  timeoutSeconds: number
): number {
  const mountedAt = useRef(Date.now());

  const getSecondsLeft = () => {
    const start = notifiedAt
      ? new Date(notifiedAt + "Z").getTime()
      : mountedAt.current;
    const elapsed = Math.floor((Date.now() - start) / 1000);
    return Math.max(0, timeoutSeconds - elapsed);
  };

  const [secondsLeft, setSecondsLeft] = useState(getSecondsLeft);

  useEffect(() => {
    setSecondsLeft(getSecondsLeft());
  }, [notifiedAt, timeoutSeconds]);

  useEffect(() => {
    const id = setInterval(() => setSecondsLeft(getSecondsLeft()), 1000);
    return () => clearInterval(id);
  }, [notifiedAt, timeoutSeconds]);

  return secondsLeft;
}

export function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
