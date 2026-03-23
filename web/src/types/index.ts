export type SlotStatus = "pending_confirmation" | "confirmed" | "declined" | "timed_out" | "withdrawn";
export type GameStatus = "open" | "in_progress" | "finished";

export interface Player {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  display_name: string;
  expo_push_token: string | null;
  is_verified: boolean;
  created_at: string;
  secret_token: string;
}

export interface Slot {
  id: number;
  player_id: number;
  position: number;
  status: SlotStatus;
  display_name: string;
  signup_number: number | null;
  notified_at: string | null;
}

export interface Game {
  id: number;
  status: GameStatus;
  max_players: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  slots: Slot[];
}

export interface QueueEntry {
  player_id: number;
  display_name: string;
  signup_number: number;
  position: number;
  joined_at: string;
}
