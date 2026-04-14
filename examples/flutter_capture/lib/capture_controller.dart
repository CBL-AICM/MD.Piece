import 'dart:async';

import 'package:flutter/foundation.dart';

import 'capture_state.dart';
import 'mock_ocr_service.dart';

class CaptureController extends ChangeNotifier {
  CaptureController({MockOcrService? service}) : _service = service ?? MockOcrService();

  final MockOcrService _service;
  Timer? _timer;

  CaptureStateModel state = const CaptureStateModel(
    status: CaptureStatus.idle,
    message: '請將文件完整放入框內',
    quality: defaultCaptureQuality,
  );

  bool autoCapture = true;

  void startDetection() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (state.status == CaptureStatus.capturing || state.status == CaptureStatus.processing) {
        return;
      }

      final evaluation = await _service.evaluate();
      state = state.copyWith(
        status: evaluation.status,
        message: evaluation.message,
        quality: evaluation.quality,
      );
      notifyListeners();

      if (autoCapture && evaluation.status == CaptureStatus.ready) {
        await capture();
      }
    });
  }

  Future<void> capture() async {
    state = state.copyWith(
      status: CaptureStatus.capturing,
      message: '拍攝中',
    );
    notifyListeners();

    await Future<void>.delayed(const Duration(milliseconds: 350));

    state = state.copyWith(
      status: CaptureStatus.processing,
      message: '正在校正與辨識',
    );
    notifyListeners();

    final result = await _service.recognize();
    state = state.copyWith(
      status: CaptureStatus.success,
      message: '辨識成功',
      recognizedText: result.text,
      confidence: result.confidence,
    );
    notifyListeners();
  }

  void reset() {
    state = const CaptureStateModel(
      status: CaptureStatus.idle,
      message: '請將文件完整放入框內',
      quality: defaultCaptureQuality,
    );
    notifyListeners();
  }

  void toggleAutoCapture(bool value) {
    autoCapture = value;
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
