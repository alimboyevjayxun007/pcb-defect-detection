export interface Detection {
  defect_type: string;
  confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
}

export type Verdict = "OK" | "NOK";

export interface InspectionResult {
  id: string;
  mode: "single" | "live";
  verdict: Verdict;
  inference_ms: number | null;
  created_at: string;
  image_url: string | null;
  detections: Detection[];
}

export interface InspectionListItem {
  id: string;
  mode: "single" | "live";
  verdict: Verdict;
  created_at: string;
  defect_count: number;
}

export interface LiveFrameResult {
  verdict: Verdict;
  inference_ms: number;
  detections: Detection[];
}

export interface DefectType {
  name: string;
  description: string | null;
}
