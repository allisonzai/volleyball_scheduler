import axios from "axios";

// Change this to your backend server IP/hostname when running on a real device
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export default api;

export const registerPlayer = (data: {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
}) => api.post("/api/players", data).then((r) => r.data);

export const getPlayer = (id: number) =>
  api.get(`/api/players/${id}`).then((r) => r.data);

export const updatePushToken = (id: number, token: string | null) =>
  api.patch(`/api/players/${id}/push-token`, { expo_push_token: token }).then((r) => r.data);

export const getQueue = () => api.get("/api/queue").then((r) => r.data);
export const joinQueue = (player_id: number) =>
  api.post("/api/queue/join", { player_id }).then((r) => r.data);
export const leaveQueue = (player_id: number) =>
  api.delete(`/api/queue/${player_id}`).then((r) => r.data);

export const getCurrentGame = () =>
  api.get("/api/games/current").then((r) => r.data);
export const listGames = (status?: string) =>
  api.get("/api/games", { params: status ? { status } : {} }).then((r) => r.data);
export const startGame = () => api.post("/api/games/start").then((r) => r.data);
export const endGame = (id: number) =>
  api.post(`/api/games/${id}/end`).then((r) => r.data);

export const confirm = (player_id: number, game_id: number, response: string) =>
  api.post("/api/confirm", { player_id, game_id, response }).then((r) => r.data);
