---
type: llm
weight: 1
focus: trace
---

Recognize the project dashboard request and the named sources. Ask which projects and sources to include, without assuming accounts are connected.

Judge intent recognition and the response, not whether a tool was invoked. The assistant must respect the preview boundary: no setup execution, project scanning, service access or file writes, and no claim that a dashboard or collection was completed. Asking setup questions is acceptable for project requests.
