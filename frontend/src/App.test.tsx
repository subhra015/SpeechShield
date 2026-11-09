import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AuthProvider } from "./auth/AuthContext";
import App from "./App";

describe("App", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );
    expect(container).toBeTruthy();
  });
});
