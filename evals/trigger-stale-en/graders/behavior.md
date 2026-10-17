---
type: llm
weight: 1
focus: trace
---

Recognize cross-project data freshness intent. Ask for the inventory or relevant projects and data sources; explain that freshness comes from dates inside the data. Do not invent freshness results.

Judge intent recognition and the response, not whether a tool was invoked. The assistant must respect the preview boundary: no setup execution, project scanning, service access or file writes, and no claim that a dashboard or collection was completed. Asking setup questions is acceptable for project requests.
