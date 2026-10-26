import type { AxiosResponse } from "axios";
import { beforeEach, describe, expect, it } from "vitest";
import { apiError, authApi, http, tokenStore } from "../lib/api";

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
});
