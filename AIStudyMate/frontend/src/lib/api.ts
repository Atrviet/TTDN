import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type {
  AgentResponse, AnalyticsOverview, ChatHistory, ChatSession, DocumentContent,
  DocumentItem, DocumentList, ProgressResponse, QuizAttempt, QuizDetail, QuizResult,
  QuizSummary, SendMessageResponse, TokenPair, User, WeakTopicsResponse,
  DueFlashcards, FlashcardDeck, FlashcardDeckSummary, FlashcardRating, FlashcardReview,
  FlashcardStats,
  StudyPlan, StudyPlanSummary, StudyTask, StudyTaskStatus,
} from "../types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
export const http = axios.create({ baseURL, timeout: 90_000 });
const refreshClient = axios.create({ baseURL, timeout: 30_000 });

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let onSessionExpired: (() => void) | null = null;
const REFRESH_KEY = "ai_studymate_refresh";

class PublicApiError extends Error {}

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
  if (error instanceof PublicApiError) return error.message;
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
  async stream(
    id: string,
    message: string,
    document_ids: string[],
    handlers: {
      onToken: (text: string) => void;
      onCitations: (citations: import("../types/api").Citation[]) => void;
      onComplete: (response: SendMessageResponse) => void;
    },
    signal: AbortSignal,
  ) {
    const request = async (token: string | null) => fetch(`${baseURL}/chat/sessions/${id}/messages/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, document_ids }),
      signal,
    });
    let response = await request(tokenStore.getAccess());
    if (response.status === 401 && tokenStore.getRefresh()) {
      try {
        refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null; });
        response = await request(await refreshPromise);
      } catch (error) {
        tokenStore.clear(); onSessionExpired?.(); throw error;
      }
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string } | null;
      throw new PublicApiError(body?.detail ?? `HTTP ${response.status}`);
    }
    if (!response.body) throw new PublicApiError("Trình duyệt không hỗ trợ streaming response.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const dispatch = (block: string) => {
      let event = "message"; const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!data.length) return;
      const payload = JSON.parse(data.join("\n"));
      if (event === "token") handlers.onToken(payload.text);
      else if (event === "citations") handlers.onCitations(payload.citations);
      else if (event === "complete") handlers.onComplete(payload);
      else if (event === "error") throw new PublicApiError(payload.message);
    };
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        dispatch(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) dispatch(buffer);
  },
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

export const flashcardsApi = {
  decks: async () => (await http.get<{ items: FlashcardDeckSummary[] }>("/flashcards/decks")).data.items,
  deck: async (id: string) => (await http.get<FlashcardDeck>(`/flashcards/decks/${id}`)).data,
  create: async (input: { title: string; description?: string; cards?: { front_text: string; back_text: string; explanation?: string }[] }) => (await http.post<FlashcardDeck>("/flashcards/decks", input)).data,
  generate: async (input: { document_ids: string[]; topic: string; card_count: number; difficulty: string; title?: string }) => (await http.post<FlashcardDeck>("/flashcards/generate", input)).data,
  due: async (deckId?: string) => (await http.get<DueFlashcards>("/flashcards/due", { params: deckId ? { deck_id: deckId } : undefined })).data,
  stats: async () => (await http.get<FlashcardStats>("/flashcards/stats")).data,
  update: async (id: string, input: { front_text?: string; back_text?: string; explanation?: string | null }) => (await http.patch<import("../types/api").Flashcard>(`/flashcards/${id}`, input)).data,
  remove: async (id: string) => { await http.delete(`/flashcards/${id}`); },
  review: async (id: string, rating: FlashcardRating) => (await http.post<FlashcardReview>(`/flashcards/${id}/review`, { rating })).data,
};

export const studyPlansApi = {
  list: async () => (await http.get<{ items: StudyPlanSummary[] }>("/study-plans")).data.items,
  get: async (id: string) => (await http.get<StudyPlan>(`/study-plans/${id}`)).data,
  generate: async (input: { goal: string; subject: string; exam_date: string; available_days: number[]; daily_available_minutes: number; preferred_session_minutes: number; difficulty: string; document_ids: string[]; timezone: string }) => (await http.post<StudyPlan>("/study-plans/generate", input)).data,
  updateTask: async (id: string, input: { status: StudyTaskStatus; actual_duration_minutes?: number; planned_start_at?: string }) => (await http.patch<StudyTask>(`/study-tasks/${id}`, input)).data,
  replan: async (id: string) => (await http.post<StudyPlan>(`/study-plans/${id}/replan`, {})).data,
  remove: async (id: string) => { await http.delete(`/study-plans/${id}`); },
};
