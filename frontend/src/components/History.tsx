import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getInspection, listInspections } from "@/api/client";
import VerdictBadge from "./VerdictBadge";

/**
 * Tekshiruvlar tarixi — backendda /api/inspections va /api/inspections/{id}
 * allaqachon mavjud edi, lekin frontendda ularni ko'rsatadigan sahifa yo'q edi.
 * Bu komponent shu bo'shliqni to'ldiradi: ro'yxat + bosilganda tafsilot.
 */
export default function History() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["inspections"],
    queryFn: () => listInspections(50),
  });

  const detailQuery = useQuery({
    queryKey: ["inspection", selectedId],
    queryFn: () => getInspection(selectedId as string),
    enabled: !!selectedId,
  });

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h2 className="text-xl font-semibold mb-4">Tekshiruvlar tarixi</h2>

      {listQuery.isLoading && <p className="text-slate-400">Yuklanmoqda...</p>}
      {listQuery.isError && (
        <p className="text-nok">Tarixni yuklab bo'lmadi: {(listQuery.error as Error).message}</p>
      )}

      {listQuery.data && listQuery.data.length === 0 && (
        <p className="text-slate-400">Hali hech qanday tekshiruv qilinmagan.</p>
      )}

      {listQuery.data && listQuery.data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <table className="w-full text-sm border border-slate-700 rounded-lg overflow-hidden self-start">
            <thead className="bg-slate-800 text-slate-300">
              <tr>
                <th className="text-left px-3 py-2">Sana</th>
                <th className="text-left px-3 py-2">Rejim</th>
                <th className="text-left px-3 py-2">Natija</th>
                <th className="text-left px-3 py-2">Nuqson</th>
              </tr>
            </thead>
            <tbody>
              {listQuery.data.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className={`cursor-pointer border-t border-slate-800 hover:bg-slate-800/60 ${
                    selectedId === item.id ? "bg-slate-800" : ""
                  }`}
                >
                  <td className="px-3 py-2 text-slate-400">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">{item.mode === "single" ? "Rasm" : "Real-time"}</td>
                  <td className="px-3 py-2">
                    <VerdictBadge verdict={item.verdict} />
                  </td>
                  <td className="px-3 py-2 text-slate-400">{item.defect_count}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="border border-slate-700 rounded-lg p-4 min-h-[160px]">
            {!selectedId && (
              <p className="text-slate-400 text-sm">
                Tafsilotlarni ko'rish uchun chapdagi ro'yxatdan bitta qatorni tanlang.
              </p>
            )}
            {selectedId && detailQuery.isLoading && (
              <p className="text-slate-400 text-sm">Yuklanmoqda...</p>
            )}
            {selectedId && detailQuery.data && (
              <div className="space-y-3">
                <VerdictBadge verdict={detailQuery.data.verdict} />
                {detailQuery.data.image_url && (
                  <img
                    src={detailQuery.data.image_url}
                    alt="Tekshiruv natijasi"
                    className="w-full rounded-lg border border-slate-700"
                  />
                )}
                <p className="text-sm text-slate-400">
                  Inference: {detailQuery.data.inference_ms?.toFixed(1) ?? "—"} ms ·{" "}
                  {detailQuery.data.detections.length} ta nuqson
                </p>
                {detailQuery.data.detections.length > 0 && (
                  <ul className="text-sm space-y-1">
                    {detailQuery.data.detections.map((d, i) => (
                      <li key={i} className="text-slate-300">
                        • {d.defect_type} — {(d.confidence * 100).toFixed(1)}% ishonch
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
