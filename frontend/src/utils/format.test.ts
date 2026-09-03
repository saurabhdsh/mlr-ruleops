import { describe, expect, it } from "vitest";
import { fmtPct, pill } from "./format";

describe("format helpers", () => {
  it("formats rates", () => {
    expect(fmtPct(0.0472)).toContain("4.72");
  });
  it("maps pass status", () => {
    expect(pill("PASS")).toContain("pass");
  });
});
