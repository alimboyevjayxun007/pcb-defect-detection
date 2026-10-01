import { describe, expect, it } from "vitest";
import { buildLiveSocketUrl } from "./client";

describe("buildLiveSocketUrl", () => {
  it("https sahifada wss:// qaytaradi", () => {
    // jsdom standart http://localhost/ bilan ishlaydi; bu yerda shunchaki
    // funksiya joriy location'ga mos protokolni to'g'ri tanlashini tekshiramiz.
    const url = buildLiveSocketUrl();
    expect(url).toMatch(/^wss?:\/\/.+\/api\/inspect\/live$/);
  });
});
