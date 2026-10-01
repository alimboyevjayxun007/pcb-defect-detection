import axios from "axios";
import type { InspectionResult, InspectionListItem, DefectType } from "@/types";

const api = axios.create({ baseURL: "/api" });

export async function inspectImage(file: File): Promise<InspectionResult> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<InspectionResult>("/inspect/image", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listInspections(limit = 50): Promise<InspectionListItem[]> {
  const { data } = await api.get<InspectionListItem[]>("/inspections", { params: { limit } });
  return data;
}

export async function getInspection(id: string): Promise<InspectionResult> {
  const { data } = await api.get<InspectionResult>(`/inspections/${id}`);
  return data;
}

export async function listDefectTypes(): Promise<DefectType[]> {
  const { data } = await api.get<DefectType[]>("/defect-types");
  return data;
}

export function buildLiveSocketUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/inspect/live`;
}

export default api;
