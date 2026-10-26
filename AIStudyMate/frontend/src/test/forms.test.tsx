import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, expect, it } from "vitest";
import { LoginPage, RegisterPage } from "../pages/AuthPages";

const login = vi.fn(); const register = vi.fn();
vi.mock("../auth/AuthProvider", () => ({ useAuth: () => ({ user: null, initializing: false, login, register, logout: vi.fn() }) }));

describe("authentication forms", () => {
  it("validates an empty login form without calling API", async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Vui lòng nhập đầy đủ");
    expect(login).not.toHaveBeenCalled();
  });

  it("validates registration fields before submit", async () => {
    render(<MemoryRouter><RegisterPage /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Họ và tên"), "An");
    await userEvent.type(screen.getByLabelText("Tên đăng nhập"), "a");
    await userEvent.type(screen.getByLabelText("Email"), "an@example.com");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(screen.getByRole("alert")).toHaveTextContent("username ≥ 3");
    expect(register).not.toHaveBeenCalled();
  });
});
