import { CaptureEvaluation, OcrResult } from "../types/capture";

const evaluations: CaptureEvaluation[] = [
  {
    captureState: "detecting",
    message: "正在偵測文件位置",
    quality: {
      alignment: "warning",
      sharpness: "warning",
      lighting: "ok",
      glare: "ok",
    },
  },
  {
    captureState: "misaligned",
    message: "請將文件完整放入框內",
    quality: {
      alignment: "error",
      sharpness: "ok",
      lighting: "ok",
      glare: "ok",
    },
  },
  {
    captureState: "glare",
    message: "反光過強，請調整拍攝角度",
    quality: {
      alignment: "ok",
      sharpness: "ok",
      lighting: "ok",
      glare: "error",
    },
  },
  {
    captureState: "ready",
    message: "已對準，可拍攝",
    quality: {
      alignment: "ok",
      sharpness: "ok",
      lighting: "ok",
      glare: "ok",
    },
  },
];

let cursor = 0;

export async function evaluateCapture(): Promise<CaptureEvaluation> {
  await delay(350);
  const evaluation = evaluations[cursor % evaluations.length];
  cursor += 1;
  return evaluation;
}

export async function recognizeDocument(): Promise<OcrResult> {
  await delay(900);
  return {
    requestId: `ocr_${Date.now()}`,
    success: true,
    confidence: 0.93,
    text: "文件名稱：MD.Piece OCR 範例\n編號：A-102948\n日期：2026-04-15",
  };
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
