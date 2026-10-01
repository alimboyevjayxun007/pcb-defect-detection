import { useCallback, useEffect, useRef, useState } from "react";
import type { LiveFrameResult } from "@/types";
import { buildLiveSocketUrl } from "@/api/client";

type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";

/**
 * PCB real-time aniqlash uchun WebSocket hook.
 * Ulanishni ochadi, frame yuborish funksiyasini va eng so'nggi natijani qaytaradi.
 * Ulanish uzilib qolsa, avtomatik qayta ulanishga harakat qiladi.
 */
export function useLiveInspection() {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [lastResult, setLastResult] = useState<LiveFrameResult | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  // Foydalanuvchi ataylab uzganini bildiradi — true bo'lsa, onclose
  // avtomatik qayta ulanishni BOSHLAMASLIGI kerak. Buning yo'qligi avvalgi
  // versiyada bug edi: disconnect() chaqirilib, socket yopilgandan keyin ham,
  // socket'ning o'z onclose handler'i (asinxron, kechroq) ishga tushib,
  // 2 soniyadan keyin fonda yangi ulanish ochib yuborardi — "to'xtatish"
  // tugmasi haqiqatda to'liq to'xtatmasdi.
  const manualCloseRef = useRef(false);

  const connect = useCallback(() => {
    manualCloseRef.current = false;
    setStatus("connecting");
    const ws = new WebSocket(buildLiveSocketUrl());

    ws.onopen = () => setStatus("open");
    ws.onclose = () => {
      if (manualCloseRef.current) {
        // Foydalanuvchi o'zi uzgan — qayta ulanmaymiz.
        setStatus("idle");
        return;
      }
      setStatus("closed");
      // 2 soniyadan keyin avtomatik qayta ulanish (faqat kutilmagan uzilishda)
      reconnectTimer.current = window.setTimeout(connect, 2000);
    };
    ws.onerror = () => setStatus("error");
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as LiveFrameResult;
        setLastResult(data);
      } catch {
        // noise frame — e'tiborsiz qoldiramiz
      }
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("idle");
  }, []);

  const sendFrame = useCallback((imageBase64: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ image_base64: imageBase64 }));
    }
  }, []);

  useEffect(() => {
    return () => {
      manualCloseRef.current = true;
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return { status, lastResult, connect, disconnect, sendFrame };
}
