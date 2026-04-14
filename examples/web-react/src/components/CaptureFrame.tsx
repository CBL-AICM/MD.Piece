import { CaptureEvaluation } from "../types/capture";

interface CaptureFrameProps {
  evaluation: CaptureEvaluation | null;
}

const statusLabels = {
  ok: "正常",
  warning: "注意",
  error: "異常",
} as const;

export function CaptureFrame({ evaluation }: CaptureFrameProps) {
  const frameState = evaluation?.captureState ?? "idle";

  return (
    <section className={`capture-frame is-${frameState}`}>
      <div className="camera-preview">
        <div className="ambient-glow" />
        <div className="document-frame" aria-hidden="true">
          <span className="corner corner-top-left" />
          <span className="corner corner-top-right" />
          <span className="corner corner-bottom-left" />
          <span className="corner corner-bottom-right" />
          <div className="frame-hint">
            {evaluation?.message ?? "請將文件完整放入框內"}
          </div>
        </div>
      </div>

      <div className="quality-grid" aria-label="拍攝品質狀態">
        <QualityPill label="對齊" value={evaluation?.quality.alignment ?? "warning"} />
        <QualityPill label="清晰" value={evaluation?.quality.sharpness ?? "warning"} />
        <QualityPill label="光線" value={evaluation?.quality.lighting ?? "warning"} />
        <QualityPill label="反光" value={evaluation?.quality.glare ?? "warning"} />
      </div>
    </section>
  );
}

function QualityPill({ label, value }: { label: string; value: "ok" | "warning" | "error" }) {
  return (
    <div className={`quality-pill is-${value}`}>
      <span>{label}</span>
      <strong>{statusLabels[value]}</strong>
    </div>
  );
}
