/* Axios API-Client fuer Planung SBP */

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { "Content-Type": "application/json" },
});

// JWT-Token automatisch anfuegen
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("sbp_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Bei 401 automatisch ausloggen (Token abgelaufen / ungueltig)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Nur ausloggen bei geschuetzten Requests (nicht bei Login-Versuch)
      const url = error.config?.url || "";
      if (!url.includes("/auth/login") && !url.includes("/auth/setup")) {
        localStorage.removeItem("sbp_token");
        localStorage.removeItem("sbp_user");
        // Kein Redirect — React State sorgt fuer Login-Anzeige
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

export default api;

/* Auth */
export const authAPI = {
  status: () => api.get("/auth/status"),
  setup: (email: string, password: string) =>
    api.post("/auth/setup", { email, password }),
  login: (type: "admin" | "musiker", email: string, password: string) =>
    api.post("/auth/login", { type, email, password }),
  setMusikerPassword: (password: string) =>
    api.post("/auth/musiker-password", { password }),
  me: () => api.get("/auth/me"),
};

/* Seasons */
export const seasonsAPI = {
  list: () => api.get("/seasons"),
  get: (id: number) => api.get(`/seasons/${id}`),
  create: (data: Record<string, unknown>) => api.post("/seasons", data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/seasons/${id}`, data),
};

/* Events */
export const eventsAPI = {
  list: (params?: Record<string, string | number>) => api.get("/events", { params }),
  get: (id: number) => api.get(`/events/${id}`),
  create: (data: Record<string, unknown>) => api.post("/events", data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/events/${id}`, data),
  delete: (id: number) => api.delete(`/events/${id}`),
  validate: (data: Record<string, unknown>) => api.post("/events/validate", data),
};

/* Projects */
export const projectsAPI = {
  list: (params?: Record<string, string | number>) => api.get("/projects", { params }),
  get: (id: number) => api.get(`/projects/${id}`),
  create: (data: Record<string, unknown>) => api.post("/projects", data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/projects/${id}`, data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  events: (id: number) => api.get(`/projects/${id}/events`),
};

/* Musicians */
export const musiciansAPI = {
  list: () => api.get("/musicians"),
  get: (id: number) => api.get(`/musicians/${id}`),
  plans: (id: number) => api.get(`/musicians/${id}/plans`),
  directory: () => api.get("/musicians/directory"),
};

/* Generator */
export const generatorAPI = {
  generate: (data: { season_id: number; start_date: string; end_date: string }) =>
    api.post("/generator/generate", data, { timeout: 300000 }), // 5 Minuten Timeout
  plans: () => api.get("/generator/plans"),
  plan: (id: number) => api.get(`/generator/plans/${id}`),
};
