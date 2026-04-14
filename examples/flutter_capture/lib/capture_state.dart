enum CaptureStatus {
  idle,
  detecting,
  misaligned,
  blurry,
  tooDark,
  glare,
  ready,
  capturing,
  processing,
  success,
  failed,
}

enum QualityLevel {
  ok,
  warning,
  error,
}

class CaptureQuality {
  const CaptureQuality({
    required this.alignment,
    required this.sharpness,
    required this.lighting,
    required this.glare,
  });

  final QualityLevel alignment;
  final QualityLevel sharpness;
  final QualityLevel lighting;
  final QualityLevel glare;
}

class CaptureStateModel {
  const CaptureStateModel({
    required this.status,
    required this.message,
    required this.quality,
    this.recognizedText,
    this.confidence,
  });

  final CaptureStatus status;
  final String message;
  final CaptureQuality quality;
  final String? recognizedText;
  final double? confidence;

  CaptureStateModel copyWith({
    CaptureStatus? status,
    String? message,
    CaptureQuality? quality,
    String? recognizedText,
    double? confidence,
  }) {
    return CaptureStateModel(
      status: status ?? this.status,
      message: message ?? this.message,
      quality: quality ?? this.quality,
      recognizedText: recognizedText ?? this.recognizedText,
      confidence: confidence ?? this.confidence,
    );
  }
}

const defaultCaptureQuality = CaptureQuality(
  alignment: QualityLevel.warning,
  sharpness: QualityLevel.warning,
  lighting: QualityLevel.warning,
  glare: QualityLevel.warning,
);
