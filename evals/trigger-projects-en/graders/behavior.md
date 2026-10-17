---
type: llm
weight: 1
focus: trace
---

Recognize a request for an overview of software projects. Explain the dashboard and ask which projects or existing inventory to use.

Judge intent recognition and the response, not whether a tool was invoked. The assistant must respect the preview boundary: no setup execution, project scanning, service access or file writes, and no claim that a dashboard or collection was completed. Asking setup questions is acceptable for project requests.
