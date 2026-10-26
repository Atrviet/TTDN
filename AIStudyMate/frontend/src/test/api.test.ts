import type { AxiosResponse } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiError, authApi, chatApi, http, tokenStore } from "../lib/api";

describe("typed API client", () => {
  beforeEach(() => { tokenStore.clear(); });

  it("encodes OAuth2 login as form data", async () => {
    let observed = "";
    http.defaults.adapter = async (config) => {
      observed = String(config.data);
      return { data: { access_token: "access", refresh_token: "refresh", token_type: "bearer" }, status: 200, statusText: "OK", headers: {}, config } as AxiosResponse;
    };
    const tokens = await authApi.login("student", "secret123");
    expect(tokens.access_token).toBe("access");
    expect(observed).toContain("username=student");
    expect(observed).toContain("password=secret123");
  });

  it("keeps access token in memory and refresh token in sessionStorage", async () => {
    tokenStore.set({ access_token: "memory-token", refresh_token: "session-token", token_type: "bearer" });
    let authorization: unknown;
    http.defaults.adapter = async (config) => {
      authorization = config.headers.Authorization;
      return { data: {}, status: 200, statusText: "OK", headers: {}, config } as AxiosResponse;
    };
    await http.get("/test");
    expect(authorization).toBe("Bearer memory-token");
    expect(sessionStorage.getItem("ai_studymate_refresh")).toBe("session-token");
    expect(localStorage.length).toBe(0);
  });

  it("returns a safe Vietnamese fallback for unknown errors", () => {
    expect(apiError(new Error("internal secret"))).toBe("Đã có lỗi xảy ra. Vui lòng thử lại.");
  });

  it("parses authenticated SSE tokens, citations and completion", async () => {
    tokenStore.set({ access_token: "access-stream", refresh_token: "refresh", token_type: "bearer" });
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: citations\ndata: {"citations":[{"document_id":"d","document_title":"Doc","page_number":1,"chunk_id":"c"}]}\n\n'));
        controller.enqueue(encoder.encode('event: token\ndata: {"text":"Xin "}\n\nevent: token\ndata: {"text":"chào"}\n\n'));
        controller.enqueue(encoder.encode('event: complete\ndata: {"session_id":"s","user_message":{},"assistant_message":{},"model":"mock"}\n\n'));
        controller.close();
      },
    });
    let authorization = ""; let observedSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(async (_url, init) => {
      authorization = String((init?.headers as Record<string, string>).Authorization);
      observedSignal = init?.signal ?? undefined;
      return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    }));
    const abort = new AbortController(); const tokens: string[] = []; let citationCount = 0; let completed = false;
    await chatApi.stream("s", "question", ["d"], {
      onToken: (text) => tokens.push(text),
      onCitations: (items) => { citationCount = items.length; },
      onComplete: () => { completed = true; },
    }, abort.signal);
    expect(authorization).toBe("Bearer access-stream");
    expect(observedSignal).toBe(abort.signal);
    expect(tokens.join("")).toBe("Xin chào");
    expect(citationCount).toBe(1);
    expect(completed).toBe(true);
    vi.unstubAllGlobals();
  });
});
