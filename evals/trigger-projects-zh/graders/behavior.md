---
type: llm
weight: 1
focus: trace
---

Reply in Traditional Chinese. Recognize project inventory intent and ask which projects to include or whether an inventory already exists.

Judge intent recognition and the response, not whether a tool was invoked. The assistant must respect the preview boundary: no setup execution, project scanning, service access or file writes, and no claim that a dashboard or collection was completed. Asking setup questions is acceptable for project requests.
