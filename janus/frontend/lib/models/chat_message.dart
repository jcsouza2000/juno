// lib/models/chat_message.dart
class ChatMessage {
  final String text;
  final bool isUser;
  final List<Map<String, dynamic>>? actions;
  final DateTime timestamp;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.actions,
    required this.timestamp,
  });
}
