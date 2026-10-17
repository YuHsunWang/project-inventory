# Trigger evals

From the repository root, run with Claude credentials:

```sh
claude plugin eval . --runs 3 --no-publish
```

Five positive cases (English / Traditional Chinese) and three near misses exercise
project-inventory routing. Each has a skill invocation check and an LLM behavior grader.
Cases allow only Skill, Read, Glob and Grep, with four turns and a 90-second timeout;
the prompt asks for a preview only, so setup and writes are outside the task.
The default no-plugin baseline runs automatically. Positive invocation graders are
with-only indicators, excluded from the comparative score; inspect those indicators
for trigger failures. Negative invocation checks use min/max 0 and arm: both.
Results stay in ignored evals/results/. --no-publish keeps the report local.
Only CLI help and local case validation were run during authoring; credentials are
required to measure trigger quality.
