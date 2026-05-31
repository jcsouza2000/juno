import axios from "axios";
import { getSession } from "next-auth/react";

const FALLBACK_API_URL = process.env.NEXT_PUBLIC_FALLBACK_API_URL || "http://localhost:8003";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

api.interceptors.request.use(async (config) => {
  const session = await getSession();
  if (session?.accessToken) {
    config.headers.Authorization = `Bearer ${session.accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    const isPilotUploadRoute =
      typeof config?.url === "string" &&
      (config.url.startsWith("/integrations/erp") || config.url.startsWith("/financials/upload"));
    const shouldTryFallback =
      isPilotUploadRoute &&
      [400, 404, 422, 500].includes(error.response?.status) &&
      !config.__junoFallbackTried;

    if (!shouldTryFallback) {
      return Promise.reject(error);
    }

    config.__junoFallbackTried = true;
    config.baseURL = FALLBACK_API_URL;
    return api.request(config);
  },
);

export function getApiErrorMessage(
  err: unknown,
  fallback = "Erro ao conectar ao servidor.",
): string {
  if (err && typeof err === "object" && "response" in err) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detail) return detail;
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const isNetworkError =
    (err &&
      typeof err === "object" &&
      "code" in err &&
      (err as { code?: string }).code === "ERR_NETWORK") ||
    (err &&
      typeof err === "object" &&
      "message" in err &&
      typeof (err as { message?: string }).message === "string" &&
      (err as { message: string }).message.includes("Network Error"));

  if (isNetworkError) {
    return `Backend indisponivel em ${apiBase}. Execute Smart_Juno.bat ou mantenha a janela "JUNO Backend :8001" aberta.`;
  }

  return fallback;
}
