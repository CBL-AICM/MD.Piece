import 'package:flutter/material.dart';

import 'capture_controller.dart';
import 'capture_state.dart';

class CapturePage extends StatefulWidget {
  const CapturePage({super.key});

  @override
  State<CapturePage> createState() => _CapturePageState();
}

class _CapturePageState extends State<CapturePage> {
  late final CaptureController controller;

  @override
  void initState() {
    super.initState();
    controller = CaptureController()..startDetection();
    controller.addListener(_onChanged);
  }

  @override
  void dispose() {
    controller.removeListener(_onChanged);
    controller.dispose();
    super.dispose();
  }

  void _onChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = controller.state;

    return Scaffold(
      backgroundColor: const Color(0xFFF3F7FC),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _GhostButton(label: '返回', onPressed: () {}),
                  const Column(
                    children: [
                      Text('文件 OCR', style: TextStyle(fontSize: 12, color: Color(0xFF5E7AA4))),
                      SizedBox(height: 4),
                      Text('拍攝文件', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
                    ],
                  ),
                  _GhostButton(label: '閃光燈', onPressed: () {}),
                ],
              ),
              const SizedBox(height: 20),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(28),
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF203A5E), Color(0xFF0D1627)],
                    ),
                  ),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: Padding(
                          padding: const EdgeInsets.all(28),
                          child: Container(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(
                                color: _frameColor(state.status),
                                width: 2,
                              ),
                            ),
                            child: Align(
                              alignment: Alignment.bottomCenter,
                              child: Container(
                                margin: const EdgeInsets.all(16),
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                                decoration: BoxDecoration(
                                  color: Colors.black.withValues(alpha: 0.35),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: Text(
                                  state.message,
                                  style: const TextStyle(color: Colors.white),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _QualityChip(label: '對齊', level: state.quality.alignment),
                  _QualityChip(label: '清晰', level: state.quality.sharpness),
                  _QualityChip(label: '光線', level: state.quality.lighting),
                  _QualityChip(label: '反光', level: state.quality.glare),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('即時狀態', style: TextStyle(fontSize: 12, color: Color(0xFF5E7AA4))),
                            const SizedBox(height: 4),
                            Text(_statusTitle(state.status), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                          ],
                        ),
                        Row(
                          children: [
                            const Text('自動拍攝'),
                            Switch(
                              value: controller.autoCapture,
                              onChanged: controller.toggleAutoCapture,
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        state.message,
                        style: const TextStyle(color: Color(0xFF385174), height: 1.5),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: controller.reset,
                            child: const Text('重新偵測'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: FilledButton(
                            onPressed: state.status == CaptureStatus.ready ? controller.capture : null,
                            child: const Text('手動拍攝'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: const Color(0xFF0F1B2E),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('辨識結果', style: TextStyle(color: Colors.white70)),
                        if (state.confidence != null)
                          Text(
                            '信心 ${(state.confidence! * 100).round()}%',
                            style: const TextStyle(color: Color(0xFF8AF0B1)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      state.recognizedText ?? '拍攝完成後將顯示 OCR 結果。',
                      style: const TextStyle(color: Color(0xFFDEECFF), height: 1.6),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GhostButton extends StatelessWidget {
  const _GhostButton({
    required this.label,
    required this.onPressed,
  });

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onPressed,
      style: TextButton.styleFrom(
        backgroundColor: const Color(0xFFE8EFF9),
        foregroundColor: const Color(0xFF2A4B73),
      ),
      child: Text(label),
    );
  }
}

class _QualityChip extends StatelessWidget {
  const _QualityChip({
    required this.label,
    required this.level,
  });

  final String label;
  final QualityLevel level;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label),
          const SizedBox(width: 8),
          Text(
            _qualityLabel(level),
            style: TextStyle(
              color: switch (level) {
                QualityLevel.ok => const Color(0xFF1F8A52),
                QualityLevel.warning => const Color(0xFFC07B19),
                QualityLevel.error => const Color(0xFFC13D33),
              },
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

Color _frameColor(CaptureStatus status) {
  return switch (status) {
    CaptureStatus.ready => const Color(0xFF76E59D),
    CaptureStatus.misaligned ||
    CaptureStatus.blurry ||
    CaptureStatus.tooDark ||
    CaptureStatus.glare =>
      const Color(0xFFFFB860),
    _ => Colors.white70,
  };
}

String _statusTitle(CaptureStatus status) {
  return switch (status) {
    CaptureStatus.idle => '等待對準',
    CaptureStatus.detecting => '正在偵測',
    CaptureStatus.misaligned => '位置不正',
    CaptureStatus.blurry => '畫面模糊',
    CaptureStatus.tooDark => '光線不足',
    CaptureStatus.glare => '反光過強',
    CaptureStatus.ready => '可拍攝',
    CaptureStatus.capturing => '拍攝中',
    CaptureStatus.processing => '辨識中',
    CaptureStatus.success => '辨識成功',
    CaptureStatus.failed => '辨識失敗',
  };
}

String _qualityLabel(QualityLevel level) {
  return switch (level) {
    QualityLevel.ok => '正常',
    QualityLevel.warning => '注意',
    QualityLevel.error => '異常',
  };
}
