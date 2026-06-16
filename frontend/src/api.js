const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  getYears: () => request("/data/draft-years"),
  getDataStatus: () => request("/data/status"),
  getYearStatus: (draftYear) => request(`/data/draft-years/${draftYear}/status`),
  buildDraftYear: (draftYear, payload = {}) => {
    const params = new URLSearchParams();
    if (payload.through_season) params.set("through_season", payload.through_season);
    if (payload.force) params.set("force", "true");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request(`/data/draft-years/${draftYear}/build${suffix}`, { method: "POST" });
  },
  getTeams: (draftYear) =>
    request(draftYear ? `/data/teams?draft_year=${draftYear}` : "/data/teams"),
  createGame: (payload) =>
    request("/games", { method: "POST", body: JSON.stringify(payload) }),
  getGame: (gameId) => request(`/games/${gameId}`),
  simulate: (gameId) =>
    request(`/games/${gameId}/simulate-until-user-pick`, { method: "POST" }),
  simulateRest: (gameId) =>
    request(`/games/${gameId}/simulate-rest`, { method: "POST" }),
  getBoard: (gameId) => request(`/games/${gameId}/draft-board`),
  getProspect: (gameId, hiddenId) => request(`/games/${gameId}/prospects/${hiddenId}`),
  makePick: (gameId, hiddenId) =>
    request(`/games/${gameId}/pick`, {
      method: "POST",
      body: JSON.stringify({ hidden_id: hiddenId }),
    }),
  reveal: (gameId) => request(`/games/${gameId}/results`),
};
