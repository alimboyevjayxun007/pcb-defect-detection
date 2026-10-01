import { useCallback, useEffect, useRef, useState } from "react";
import { useLiveInspection } from "@/hooks/useLiveInspection";
import VerdictBadge from "./VerdictBadge";
import DetectionCanvas from "./DetectionCanvas";

const FRAME_INTERVAL_MS = 250; // ~4 FPS backendga yuborish (CPU inference uchun yetarli)
const JPEG_QUALITY = 0.7;

export default function LiveDetection() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [videoDims, setVideoDims] = useState({ width: 640, height: 480 });
  const { status, lastResult, connect, disconnect, sendFrame } = useLiveInspection();

  async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
    });
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setVideoDims({
        width: videoRef.current.videoWidth,
        height: videoRef.current.videoHeight,
      });
    }
    connect();
    setIsStreaming(true);
  }

  const stopCamera = useCallback(() => {
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((t) => t.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
    disconnect();
    setIsStreaming(false);
  }, [disconnect]);

  // Har FRAME_INTERVAL_MS'da video frame'ni yaqib, WebSocket orqali yuboradi
  useEffect(() => {
    if (!isStreaming || status !== "open") return;

    const interval = setInterval(() => {
      const video = videoRef.current;
      const canvas = captureCanvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
      sendFrame(dataUrl);
    }, FRAME_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isStreaming, status, sendFrame]);

  // Komponent unmount bo'lganda kamerani to'xtatish
  useEffect(() => stopCamera, [stopCamera]);

  const displayWidth = 640;
  const displayHeight = Math.round((videoDims.height / videoDims.width) * displayWidth) || 480;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-xl font-semibold mb-4">Real-time tekshiruv (kamera)</h2>

      <div className="flex gap-3 mb-4">
        {!isStreaming ? (
          <button
            onClick={startCamera}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
          >
            Kamerani yoqish
          </button>
        ) : (
          <button
            onClick={stopCamera}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium"
          >
            To'xtatish
          </button>
        )}
        <span className="text-sm text-slate-400 self-center">
          Ulanish holati: {status}
        </span>
      </div>

      <div
        className="relative inline-block border border-slate-700 rounded-lg overflow-hidden"
        style={{ width: displayWidth, height: displayHeight }}
      >
        <video
          ref={videoRef}
          muted
          playsInline
          style={{ width: displayWidth, height: displayHeight, objectFit: "cover" }}
        />
        {lastResult && (
          <DetectionCanvas
            sourceWidth={videoDims.width}
            sourceHeight={videoDims.height}
            displayWidth={displayWidth}
            displayHeight={displayHeight}
            detections={lastResult.detections}
          />
        )}
      </div>

      {/* Yashirin canvas — faqat frame olish uchun, ekranda ko'rsatilmaydi */}
      <canvas ref={captureCanvasRef} className="hidden" />

      {lastResult && (
        <div className="mt-4 space-y-2">
          <VerdictBadge verdict={lastResult.verdict} />
          <p className="text-sm text-slate-400">
            Inference: {lastResult.inference_ms.toFixed(1)} ms · {lastResult.detections.length} ta nuqson
          </p>
        </div>
      )}
    </div>
  );
}
