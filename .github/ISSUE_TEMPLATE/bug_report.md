---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

## Describe the bug
A clear and concise description of what the bug is.

## To Reproduce
Steps to reproduce the behavior:
1. Start JARVIS with '...'
2. Say '...'
3. See error

## Expected behavior
A clear and concise description of what you expected to happen.

## Actual behavior
What actually happened.

## Screenshots / Logs
If applicable, add screenshots or paste logs from `listener.log`.

## Environment
- **OS**: [e.g. Windows 11]
- **Python version**: [e.g. 3.12.5]
- **Open-Jarvis version**: [e.g. 1.0.0]
- **Ollama version** (if used): [e.g. 0.3.12]
- **Ollama model** (if used): [e.g. tinyllama]

## Additional context
Add any other context about the problem here.

## Health check
Run `python -c "import sys; sys.path.insert(0, '.'); from core.test_suite import TestSuite; t = TestSuite(); t.run_all()"` and paste the result.
