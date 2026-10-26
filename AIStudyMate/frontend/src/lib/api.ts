import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type {
  AgentResponse, AnalyticsOverview, ChatHistory, ChatSession, DocumentContent,
  DocumentItem, DocumentList, ProgressResponse, QuizAttempt, QuizDetail, QuizResult,
  QuizSummary, SendMessageResponse, TokenPair, User, WeakTopicsResponse,
} from "../types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
export const http = axios.create({ baseURL, timeout: 90_000 });
const refreshClient = axios.create({ baseURL, timeout: 30_000 });

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let onSessionExpired: (() => void) | null = null;
const REFRESH_KEY = "ai_studymate_refresh";

export const tokenStore = {
  getAccess: () => accessToken,
  getRefresh: () => sessionStorage.getItem(REFRESH_KEY),
  set(tokens: TokenPair) {
    accessToken = tokens.access_token;
    sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() { accessToken = null; sessionStorage.removeItem(REFRESH_KEY); },
};

export function configureSessionExpiry(callback: () => void) { onSessionExpired = callback; }

http.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

async function refreshAccessToken(): Promise<string> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) throw new Error("No refresh token");
  const { data } = await refreshClient.post<TokenPair>("/auth/refresh", { refresh_token: refresh });
  tokenStore.set(data);
  return data.access_token;
}

http.interceptors.response.use(undefined, async (error: AxiosError) => {
  const request = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  if (error.response?.status !== 401 || !request || request._retry || request.url?.includes("/auth/")) {
    throw error;
  }
  request._retry = true;
  try {
    refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null; });
    const token = await refreshPromise;
    request.headers.Authorization = `Bearer ${token}`;
    return http(request);
  } catch (refreshError) {
    tokenStore.clear();
    onSessionExpired?.();
    throw refreshError;
  }
});

export function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join(", ");
    if (error.code === "ECONNABORTED") return "Yêu cầu đã hết thời gian chờ.";
  }
  return "Đã có lỗi xảy ra. Vui lòng thử lại.";
}

export const authApi = {
  async login(username: string, password: string) {
    const body = new URLSearchParams({ username, password });
    return (await http.post<TokenPair>("/auth/login", body, { headers: { "Content-Type": "application/x-www-form-urlencoded" } })).data;
  },
  async register(input: { username: string; email: string; password: string; full_name: string }) {
    return (await http.post<User>("/auth/register", input)).data;
  },
  async refresh() { const token = await refreshAccessToken(); return token; },
  async me() { return (await http.get<User>("/users/me")).data; },
};

export const documentsApi = {
  list: async (page = 1) => (await http.get<DocumentList>("/documents", { params: { page, per_page: 20 } })).data,
  get: async (id: string) => (await http.get<DocumentItem>(`/documents/${id}`)).data,
  content: async (id: string) => (await http.get<DocumentContent>(`/documents/${id}/content`)).data,
  index: async (id: string) => (await http.post(`/documents/${id}/index`)).data,
  remove: async (id: string) => { await http.delete(`/documents/${id}`); },
  async upload(title: string, file: File, onProgress: (percent: number) => void) {
    const form = new FormData(); form.append("title", title); form.append("file", file);
    return (await http.post<DocumentItem>("/documents/upload", form, {
      onUploadProgress: (event) => onProgress(event.total ? Math.round((event.loaded * 100) / event.total) : 0),
    })).data;
  },
};

export const chatApi = {
  sessions: async () => (await http.get<{ items: ChatSession[] }>("/chat/sessions")).data.items,
  create: async (title: string) => (await http.post<ChatSession>("/chat/sessions", { title })).data,
  history: async (id: string) => (await http.get<ChatHistory>(`/chat/sessions/${id}/messages`)).data,
  send: async (id: string, message: string, document_ids: string[]) => (await http.post<SendMessageResponse>(`/chat/sessions/${id}/messages`, { message, document_ids })).data,
};

export const agentApi = {
  chat: async (session_id: string, message: string, document_ids: string[]) => (await http.post<AgentResponse>("/agent/chat", { session_id, message, document_ids })).data,
};

export const quizzesApi = {
  list: async () => (await http.get<{ items: QuizSummary[] }>("/quizzes")).data.items,
  get: async (id: string) => (await http.get<QuizDetail>(`/quizzes/${id}`)).data,
  generate: async (input: { title: string; number_of_questions: number; difficulty: string; document_id: string }) => (await http.post<QuizDetail>("/quizzes/generate", input)).data,
  start: async (id: string) => (await http.post<QuizAttempt>(`/quizzes/${id}/attempts`)).data,
  submit: async (id: string, answers: { question_id: string; selected_option_id: string }[]) => (await http.post<QuizResult>(`/quizzes/attempts/${id}/submit`, { answers })).data,
  results: async (id: string) => (await http.get<QuizResult>(`/quizzes/attempts/${id}/results`)).data,
};

export const analyticsApi = {
  overview: async () => (await http.get<AnalyticsOverview>("/analytics/overview")).data,
  progress: async () => (await http.get<ProgressResponse>("/analytics/progress")).data,
  weakTopics: async () => (await http.get<WeakTopicsResponse>("/analytics/weak-topics")).data,
};
