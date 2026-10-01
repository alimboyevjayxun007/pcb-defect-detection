import { useEffect, useRef } from "react";
import type { Detection } from "@/types";

interface Props {
  /** Asl tasvir o'lchami (model bergan koordinatalar shu asosda) */
  sourceWidth: number;
  sourceHeight: number;
  /** Canvas qanday o'lchamda ko'rsatilsin (CSS piksellarda) */
  displayWidth: number;
  displayHeight: number;
  detections: Detection[];
}

const COLORS: Record<string, string> = {
  mouse_bite: "#f97316",
  missing_hole: "#ef4444",
  spurious_copper: "#eab308",
  spur: "#a855f7",
  open_circuit: "#06b6d4",
  short: "#dc2626",
};

export default function DetectionCanvas({
  sourceWidth,
  sourceHeight,
  displayWidth,
  displayHeight,
  detections,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = displayWidth;
    canvas.height = displayHeight;
    ctx.clearRect(0, 0, displayWidth, displayHeight);

    const scaleX = displayWidth / sourceWidth;
    const scaleY = displayHeight / sourceHeight;

    detections.forEach((det) => {
      const x = det.bbox_x * scaleX;
      const y = det.bbox_y * scaleY;
      const w = det.bbox_w * scaleX;
      const h = det.bbox_h * scaleY;
      const color = COLORS[det.defect_type] ?? "#dc2626";

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      const label = `${det.defect_type} ${(det.confidence * 100).toFixed(0)}%`;
      ctx.font = "12px sans-serif";
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(x, Math.max(0, y - 16), textWidth + 8, 16);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, x + 4, Math.max(12, y - 4));
    });
  }, [detections, sourceWidth, sourceHeight, displayWidth, displayHeight]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{ width: displayWidth, height: displayHeight }}
    />
  );
}
