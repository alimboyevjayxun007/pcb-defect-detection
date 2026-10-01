import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { inspectImage } from "@/api/client";
import type { InspectionResult } from "@/types";
import VerdictBadge from "./VerdictBadge";
import DetectionCanvas from "./DetectionCanvas";

const MAX_FILE_BYTES = 15 * 1024 * 1024; // backenddagi MAX_UPLOAD_BYTES bilan mos

export default function ImageUpload() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageDims, setImageDims] = useState({ width: 1, height: 1 });
  const [clientError, setClientError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation<InspectionResult, Error, File>({
    mutationFn: inspectImage,
  });

  // Har safar yangi previewUrl o'rnatilganda, eskisini tozalaymiz —
  // aks holda har bir yuklangan rasm uchun object URL browser xotirasida
  // to'planib qolaveradi (hech qachon bo'shatilmaydigan memory leak edi).
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setClientError(null);

    if (!file.type.startsWith("image/")) {
      setClientError("Faqat rasm fayllari qabul qilinadi");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setClientError(
        `Fayl juda katta (${(file.size / 1024 / 1024).toFixed(1)} MB) — max ${MAX_FILE_BYTES / 1024 / 1024} MB`
      );
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return url;
    });

    const img = new Image();
    img.onload = () => setImageDims({ width: img.naturalWidth, height: img.naturalHeight });
    img.src = url;

    mutation.mutate(file);
  }

  const displayWidth = 640;
  const displayHeight = Math.round((imageDims.height / imageDims.width) * displayWidth) || 480;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-xl font-semibold mb-4">Rasm orqali tekshirish</h2>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        className="block w-full text-sm mb-4 file:mr-4 file:py-2 file:px-4 file:rounded-lg
                   file:border-0 file:bg-blue-600 file:text-white hover:file:bg-blue-700"
      />

      {clientError && <p className="text-nok">{clientError}</p>}
      {mutation.isPending && <p className="text-slate-400">Tahlil qilinmoqda...</p>}
      {mutation.isError && <p className="text-nok">Xatolik: {mutation.error.message}</p>}

      {previewUrl && (
        <div className="relative inline-block mt-4 border border-slate-700 rounded-lg overflow-hidden">
          <img src={previewUrl} alt="Yuklangan PCB" style={{ width: displayWidth, height: displayHeight }} />
          {mutation.data && (
            <DetectionCanvas
              sourceWidth={imageDims.width}
              sourceHeight={imageDims.height}
              displayWidth={displayWidth}
              displayHeight={displayHeight}
              detections={mutation.data.detections}
            />
          )}
        </div>
      )}

      {mutation.data && (
        <div className="mt-4 space-y-2">
          <VerdictBadge verdict={mutation.data.verdict} />
          <p className="text-sm text-slate-400">
            Inference vaqti: {mutation.data.inference_ms?.toFixed(1)} ms ·{" "}
            {mutation.data.detections.length} ta nuqson topildi
          </p>
          {mutation.data.detections.length > 0 && (
            <ul className="text-sm space-y-1">
              {mutation.data.detections.map((d, i) => (
                <li key={i} className="text-slate-300">
                  • {d.defect_type} — {(d.confidence * 100).toFixed(1)}% ishonch
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
