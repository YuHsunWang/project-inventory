---
max_turns: 6
timeout_seconds: 90
allowed_tools: [Skill, Read, Glob, Grep]
---

Inventory my projects.

For this read-only routing evaluation, assume the inventory folder's inventory.json
is absent. Load the skill normally, then report which workflow you would follow
and its next action. Stop before execution or setup questions. Do not access any
real inventory folder, run discovery, or create files. Describe the workflow far
enough to distinguish what happens before and after the first page is delivered.
