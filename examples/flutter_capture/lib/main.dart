import 'package:flutter/material.dart';

import 'capture_page.dart';

void main() {
  runApp(const MdPieceCaptureApp());
}

class MdPieceCaptureApp extends StatelessWidget {
  const MdPieceCaptureApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MD.Piece Capture Demo',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2F7CF6)),
        useMaterial3: true,
      ),
      home: const CapturePage(),
    );
  }
}
