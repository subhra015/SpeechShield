import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import Login from "./Login";

describe("Login", () => {
  it("renders sign in form", () => {
    render(
      <AuthProvider>
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      </AuthProvider>
    );
    expect(screen.getByPlaceholderText("Username")).toBeInTheDocument();
    expect(
  screen.getByRole("heading", { name: /^Sign in$/i })
).toBeInTheDocument();

expect(
  screen.getByRole("button", { name: /^Sign in$/i })
).toBeInTheDocument();
  });
});
