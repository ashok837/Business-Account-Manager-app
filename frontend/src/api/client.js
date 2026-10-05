import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_URL });

// Attach the JWT access token (if present) to every outgoing request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function clearSessionAndRedirect() {
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
  localStorage.removeItem("tenant");
  window.location.href = "/login";
}

let refreshPromise = null;

/**
 * If the access token expired (401), try exchanging the refresh token for a
 * new one and retry the original request once, before giving up and sending
 * the user back to login. This keeps people logged in through short access
 * token lifetimes without re-entering their password every 30 minutes.
 */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthEndpoint = original?.url?.includes("/auth/login") || original?.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) {
        clearSessionAndRedirect();
        return Promise.reject(error);
      }
      try {
        // Only ever run one refresh at a time, even if several requests 401 together
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken })
            .finally(() => { refreshPromise = null; });
        }
        const refreshRes = await refreshPromise;
        localStorage.setItem("token", refreshRes.data.access_token);
        original.headers.Authorization = `Bearer ${refreshRes.data.access_token}`;
        return api(original);
      } catch {
        clearSessionAndRedirect();
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401 && isAuthEndpoint === false) {
      clearSessionAndRedirect();
    }
    return Promise.reject(error);
  }
);

export default api;
export { API_URL };
