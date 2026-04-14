import 'capture_state.dart';

class MockCaptureEvaluation {
  const MockCaptureEvaluation({
    required this.status,
    required this.message,
    required this.quality,
  });

  final CaptureStatus status;
  final String message;
  final CaptureQuality quality;
}

class MockOcrResult {
  const MockOcrResult({
    required this.text,
    required this.confidence,
  });

  final String text;
  final double confidence;
}

class MockOcrService {
  final List<MockCaptureEvaluation> _evaluations = const [
    MockCaptureEvaluation(
      status: CaptureStatus.detecting,
      message: '正在偵測文件位置',
      quality: CaptureQuality(
        alignment: QualityLevel.warning,
        sharpness: QualityLevel.warning,
        lighting: QualityLevel.ok,
        glare: QualityLevel.ok,
      ),
    ),
    MockCaptureEvaluation(
      status: CaptureStatus.misaligned,
      message: '請將文件完整放入框內',
      quality: CaptureQuality(
        alignment: QualityLevel.error,
        sharpness: QualityLevel.ok,
        lighting: QualityLevel.ok,
        glare: QualityLevel.ok,
      ),
    ),
    MockCaptureEvaluation(
      status: CaptureStatus.ready,
      message: '已對準，可拍攝',
      quality: CaptureQuality(
        alignment: QualityLevel.ok,
        sharpness: QualityLevel.ok,
        lighting: QualityLevel.ok,
        glare: QualityLevel.ok,
      ),
    ),
  ];

  int _cursor = 0;

  Future<MockCaptureEvaluation> evaluate() async {
    await Future<void>.delayed(const Duration(milliseconds: 400));
    final item = _evaluations[_cursor % _evaluations.length];
    _cursor += 1;
    return item;
  }

  Future<MockOcrResult> recognize() async {
    await Future<void>.delayed(const Duration(milliseconds: 900));
    return const MockOcrResult(
      text: '文件名稱：MD.Piece Flutter 範例\n編號：F-204810\n日期：2026-04-15',
      confidence: 0.91,
    );
  }
}
