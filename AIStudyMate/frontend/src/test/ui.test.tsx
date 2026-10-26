import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState } from "../components/ui";

describe("shared states", () => {
  it("renders accessible empty content", () => {
    render(<EmptyState title="Không có dữ liệu" description="Hãy bắt đầu." />);
    expect(screen.getByText("Không có dữ liệu")).toBeVisible();
  });
  it("allows retrying an error", async () => {
    const retry = vi.fn(); render(<ErrorState message="Mất kết nối" retry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Mất kết nối");
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
