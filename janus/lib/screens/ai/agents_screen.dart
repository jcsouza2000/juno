import 'package:flutter/material.dart';

class AgentsScreen extends StatefulWidget {
  const AgentsScreen({Key? key}) : super(key: key);
  @override State<AgentsScreen> createState() => _AgentsScreenState();
}

class _AgentsScreenState extends State<AgentsScreen> {
  final TextEditingController _taskController = TextEditingController();

  @override Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Agents')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _taskController,
              decoration: const InputDecoration(
                labelText: 'Task Description...',
                hintText: 'e.g., Analyze sales data and generate report',
              ),
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.send),
              label: const Text('Submit Task'),
            ),
            const SizedBox(height: 16),
            const Text('Active Agents:', style: TextStyle(fontWeight: FontWeight.bold)),
            const ListTile(
              leading: Icon(Icons.smart_toy),
              title: Text('Data Analyst'),
              subtitle: Text('Analyzes data and generates insights'),
            ),
            const ListTile(
              leading: Icon(Icons.smart_toy),
              title: Text('Report Generator'),
              subtitle: Text('Creates formatted reports from data'),
            ),
          ],
        ),
      ),
    );
  }
}
