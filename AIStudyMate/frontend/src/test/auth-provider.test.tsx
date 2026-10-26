import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, expect, it } from "vitest";
import { AuthProvider, useAuth } from "../auth/AuthProvider";
import { authApi, tokenStore } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, authApi: { login: vi.fn(), register: vi.fn(), refresh: vi.fn(), me: vi.fn() } };
});

const user = { id: "u1", username: "student", email: "student@example.com", full_name: "Student", role: "student" as const, is_active: true, created_at: "2026-01-01", updated_at: "2026-01-01" };
function Probe() { const { user: current, initializing } = useAuth(); return <div>{initializing ? "loading" : current?.full_name ?? "guest"}</div>; }

describe("authentication flow", () => {
  it("restores a session by refreshing then loading /users/me", async () => {
    sessionStorage.setItem("ai_studymate_refresh", "refresh-token");
    vi.mocked(authApi.refresh).mockResolvedValue("access-token");
    vi.mocked(authApi.me).mockResolvedValue(user);
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByText("loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Student")).toBeInTheDocument());
    expect(authApi.refresh).toHaveBeenCalledOnce();
    expect(authApi.me).toHaveBeenCalledOnce();
  });

  it("clears an invalid refresh session", async () => {
    tokenStore.set({ access_token: "old", refresh_token: "bad", token_type: "bearer" });
    vi.mocked(authApi.refresh).mockRejectedValue(new Error("expired"));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("guest")).toBeInTheDocument());
    expect(sessionStorage.getItem("ai_studymate_refresh")).toBeNull();
  });
});
