import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error?.config as (typeof error.config & { _retry?: boolean }) | undefined;

    if (error?.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

      if (!refreshToken) {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        return Promise.reject(new Error("Session expired"));
      }

      try {
        const refreshResponse = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const newAccessToken = refreshResponse.data?.access_token as string | undefined;
        const newRefreshToken = (refreshResponse.data?.refresh_token as string | undefined) ?? refreshToken;

        if (!newAccessToken) {
          throw new Error("Invalid refresh response");
        }

        localStorage.setItem(ACCESS_TOKEN_KEY, newAccessToken);
        localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem("auth_user");
        return Promise.reject(new Error("Session expired. Please login again."));
      }
    }

    const detail = error?.response?.data?.detail;
    const message = typeof detail === "string" ? detail : error.message ?? "Request failed";
    return Promise.reject(new Error(message));
  }
);

export { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY };
