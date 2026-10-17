---
type: llm
weight: 1
focus: trace
---

Treat this as a single-repository Git question. Explain git branch (and optionally git branch -a) or ask which repository. Do not claim to have listed branches or start a cross-project dashboard.

Judge intent recognition and the response, not whether a tool was invoked. The assistant must respect the preview boundary: no setup execution, project scanning, service access or file writes, and no claim that a dashboard or collection was completed. Asking setup questions is acceptable for project requests.
