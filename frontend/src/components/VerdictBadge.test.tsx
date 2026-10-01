import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import VerdictBadge from "./VerdictBadge";

describe("VerdictBadge", () => {
  it("OK uchun 'YAROQLI' matnini ko'rsatadi", () => {
    render(<VerdictBadge verdict="OK" />);
    expect(screen.getByText(/YAROQLI/)).toBeInTheDocument();
  });

  it("NOK uchun 'YAROQSIZ' matnini ko'rsatadi", () => {
    render(<VerdictBadge verdict="NOK" />);
    expect(screen.getByText(/YAROQSIZ/)).toBeInTheDocument();
  });
});
