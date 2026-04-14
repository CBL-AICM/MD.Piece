import { useEffect, useState } from "react";
import { CaptureFrame } from "./components/CaptureFrame";
import { evaluateCapture, recognizeDocument } from "./services/mockOcrApi";
import { CaptureEvaluation, CaptureState, OcrResult } from "./types/capture";

export default function App() {
  const [captureState, setCaptureState] = useState<CaptureState>("idle");
  const [autoCapture, setAutoCapture] = useState(true);
  const [evaluation, setEvaluation] = useState<CaptureEvaluation | null>(null);
  const [ocrResult, setOcrResult] = useState<OcrResult | null>(null);

  useEffect(() => {
    if (captureState === "success") {
      return;
    }

    const timer = window.setInterval(async () => {
      if (captureState === "capturing" || captureState === "processing") {
        return;
      }

      const nextEvaluation = await evaluateCapture();
      setEvaluation(nextEvaluation);
      setCaptureState(nextEvaluation.captureState);

      if (autoCapture && nextEvaluation.captureState === "ready") {
        window.clearInterval(timer);
        void handleCapture();
      }
    }, 1600);

    return () => window.clearInterval(timer);
  }, [autoCapture, captureState]);

  async function handleCapture() {
    setOcrResult(null);
    setCaptureState("capturing");
    await wait(400);
    setCaptureState("processing");

    const result = await recognizeDocument();
    setOcrResult(result);
    setCaptureState("success");
  }

  function handleReset() {
    setCaptureState("idle");
    setEvaluation(null);
    setOcrResult(null);
  }

  return (
    <main className="page-shell">
      <section className="phone-shell">
        <header className="app-header">
          <button className="ghost-button" type="button">
            返回
          </button>
          <div>
            <p className="eyebrow">文件 OCR</p>
            <h1>拍攝文件</h1>
          </div>
          <button className="ghost-button" type="button">
            閃光燈
          </button>
        </header>

        <CaptureFrame evaluation={evaluation} />

        <section className="panel">
          <div className="status-row">
            <div>
              <p className="eyebrow">即時狀態</p>
              <h2>{resolveStatusTitle(captureState)}</h2>
            </div>
            <label className="toggle">
              <input
                checked={autoCapture}
                onChange={(event) => setAutoCapture(event.target.checked)}
                type="checkbox"
              />
              自動拍攝
            </label>
          </div>

          <p className="status-message">
            {evaluation?.message ?? "將文件放入中央框內，系統會持續檢查品質"}
          </p>

          <div className="action-row">
            <button className="secondary-button" onClick={handleReset} type="button">
              重新偵測
            </button>
            <button
              className="primary-button"
              disabled={captureState !== "ready"}
              onClick={() => void handleCapture()}
              type="button"
            >
              手動拍攝
            </button>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="status-row">
            <div>
              <p className="eyebrow">辨識結果</p>
              <h2>{ocrResult ? "OCR 完成" : "等待拍攝"}</h2>
            </div>
            {ocrResult ? (
              <span className="confidence-badge">
                信心 {Math.round(ocrResult.confidence * 100)}%
              </span>
            ) : null}
          </div>

          <pre className="ocr-output">
            {ocrResult?.text ?? "拍攝後將在這裡顯示 OCR 文字結果。"}
          </pre>
        </section>
      </section>
    </main>
  );
}

function resolveStatusTitle(state: CaptureState) {
  switch (state) {
    case "idle":
      return "等待對準";
    case "detecting":
      return "正在偵測";
    case "misaligned":
      return "位置不正";
    case "blurry":
      return "畫面模糊";
    case "too_dark":
      return "光線不足";
    case "glare":
      return "反光過強";
    case "ready":
      return "可拍攝";
    case "capturing":
      return "拍攝中";
    case "processing":
      return "辨識中";
    case "success":
      return "辨識成功";
    case "failed":
      return "辨識失敗";
  }
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
