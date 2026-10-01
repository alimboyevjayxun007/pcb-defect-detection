import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLiveInspection } from "./useLiveInspection";

/**
 * Soxta WebSocket — haqiqiy tarmoqsiz, hook'ning reconnect mantiqini
 * sinab ko'rish uchun. `close()` chaqirilganda, haqiqiy browser'dagi kabi
 * `onclose` handler'ini chaqiradi (bu — avvalgi bug aynan shu joyda edi:
 * `disconnect()` socket'ni yopgandan keyin ham `onclose` ishga tushib,
 * yana qayta ulanishni rejalashtirardi).
 */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  send() {
    // test uchun kerak emas
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useLiveInspection — reconnect mantiqi", () => {
  it("disconnect() chaqirilgandan keyin avtomatik qayta ulanmasligi kerak (tuzatilgan bug)", () => {
    const { result } = renderHook(() => useLiveInspection());

    act(() => result.current.connect());
    expect(FakeWebSocket.instances).toHaveLength(1);

    act(() => result.current.disconnect());
    // disconnect() socket.close()ni chaqiradi -> fake socket onclose'ni
    // sinxron ishga tushiradi (haqiqiy browser'da asinxron bo'ladi, lekin
    // natija bir xil bo'lishi kerak: reconnect REJALASHTIRILMAYDI).
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(result.current.status).toBe("idle");
  });

  it("kutilmagan uzilishda (disconnect() chaqirilmasdan) 2 soniyadan keyin qayta ulanishi kerak", () => {
    const { result } = renderHook(() => useLiveInspection());

    act(() => result.current.connect());
    expect(FakeWebSocket.instances).toHaveLength(1);

    // Server tomondan yoki tarmoq muammosi bilan kutilmagan uzilish —
    // disconnect() chaqirilmagan, socket'ning o'zi yopilgan.
    act(() => {
      FakeWebSocket.instances[0].close();
    });

    act(() => {
      vi.advanceTimersByTime(2100);
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("komponent unmount bo'lganda ham qayta ulanmasligi kerak", () => {
    const { result, unmount } = renderHook(() => useLiveInspection());

    act(() => result.current.connect());
    expect(FakeWebSocket.instances).toHaveLength(1);

    unmount();
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
