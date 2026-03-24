import axios from "axios";

const BASE = import.meta.env.VITE_API_URL ?? "";

const api = axios.create({
  baseURL: `${BASE}/api`,
  headers: { "Content-Type": "application/json" },
});

export default api;

// Players
export const registerPlayer = (data: {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  password: string;
}) => api.post("/players", data).then((r) => r.data);

export const getPlayer = (id: number) =>
  api.get(`/players/${id}`).then((r) => r.data);

export const signIn = (phone: string, password: string) =>
  api.post("/players/signin", { phone, password }).then((r) => r.data);

export const requestVerification = (id: number, channel: string) =>
  api.post(`/players/${id}/request-verification`, { channel }).then((r) => r.data);

export const submitVerification = (id: number, code: string) =>
  api.post(`/players/${id}/verify`, { code }).then((r) => r.data);

export const deregisterPlayer = (id: number, secret_token: string) =>
  api.delete(`/players/${id}`, { headers: { "X-Player-Token": secret_token } });

export const updatePushToken = (id: number, token: string | null) =>
  api.patch(`/players/${id}/push-token`, { expo_push_token: token }).then((r) => r.data);

// Queue
export const getQueue = () => api.get("/queue").then((r) => r.data);
export const joinQueue = (player_id: number, secret_token: string) =>
  api.post("/queue/join", { player_id }, { headers: { "X-Player-Token": secret_token } }).then((r) => r.data);
export const leaveQueue = (player_id: number, secret_token: string) =>
  api.delete(`/queue/${player_id}`, { headers: { "X-Player-Token": secret_token } }).then((r) => r.data);
export const deferQueue = (player_id: number, secret_token: string) =>
  api.post(`/queue/${player_id}/defer`, null, { headers: { "X-Player-Token": secret_token } }).then((r) => r.data);

// Games
export const getCurrentGame = () =>
  api.get("/games/current").then((r) => r.data);
export const listGames = (status?: string) =>
  api.get("/games", { params: status ? { status } : {} }).then((r) => r.data);
export const startGame = (operatorSecret: string) =>
  api.post("/games/start", null, { headers: { "X-Operator-Secret": operatorSecret } }).then((r) => r.data);
export const resetAll = (operatorSecret: string) =>
  api.post("/games/reset", null, { headers: { "X-Operator-Secret": operatorSecret } });
export const clearHistory = (operatorSecret: string) =>
  api.delete("/games/history", { headers: { "X-Operator-Secret": operatorSecret } });
export const beginGame = (id: number, operatorSecret: string) =>
  api.post(`/games/${id}/begin`, null, { headers: { "X-Operator-Secret": operatorSecret } }).then((r) => r.data);
export const endGame = (id: number, operatorSecret: string) =>
  api.post(`/games/${id}/end`, null, { headers: { "X-Operator-Secret": operatorSecret } }).then((r) => r.data);
export const leaveGame = (gameId: number, secretToken: string) =>
  api.post(`/games/${gameId}/leave`, null, { headers: { "X-Player-Token": secretToken } });

// Settings
export const getSettings = () =>
  api.get("/settings").then((r) => r.data);
export const updateSettings = (
  confirm_timeout_seconds: number,
  fill_wait_seconds: number,
  operatorSecret: string,
) =>
  api
    .patch(
      "/settings",
      { confirm_timeout_seconds, fill_wait_seconds },
      { headers: { "X-Operator-Secret": operatorSecret } },
    )
    .then((r) => r.data);

// Activity log
export const getActivity = (limit = 200) =>
  api.get("/activity", { params: { limit } }).then((r) => r.data);
export const clearActivity = (operatorSecret: string) =>
  api.delete("/activity", { headers: { "X-Operator-Secret": operatorSecret } });

// Confirmation
export const confirm = (player_id: number, game_id: number, response: string, secret_token: string) =>
  api.post("/confirm", { player_id, game_id, response }, { headers: { "X-Player-Token": secret_token } }).then((r) => r.data);
