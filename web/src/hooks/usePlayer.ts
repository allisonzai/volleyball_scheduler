import { useState, useEffect } from "react";
import type { Player } from "../types";

const STORAGE_KEY = "vb_player";

export function usePlayer() {
  const [player, setPlayerState] = useState<Player | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const setPlayer = (p: Player | null) => {
    if (p) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    setPlayerState(p);
  };

  return { player, setPlayer };
}
