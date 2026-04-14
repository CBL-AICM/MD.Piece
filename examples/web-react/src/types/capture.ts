export type CaptureState =
  | "idle"
  | "detecting"
  | "misaligned"
  | "blurry"
  | "too_dark"
  | "glare"
  | "ready"
  | "capturing"
  | "processing"
  | "success"
  | "failed";

export type QualityStatus = "ok" | "warning" | "error";

export interface CaptureQuality {
  alignment: QualityStatus;
  sharpness: QualityStatus;
  lighting: QualityStatus;
  glare: QualityStatus;
}

export interface CaptureEvaluation {
  captureState: Exclude<CaptureState, "idle" | "capturing" | "processing" | "success" | "failed">;
  message: string;
  quality: CaptureQuality;
}

export interface OcrResult {
  requestId: string;
  success: boolean;
  confidence: number;
  text: string;
}
