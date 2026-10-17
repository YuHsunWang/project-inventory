# Trigger evals

From the repository root, run with Claude credentials:

```sh
claude plugin eval . --runs 3 --no-publish
```

Five positive cases (English / Traditional Chinese) and three near misses measure
whether the project-inventory Skill fires for a bare user request. The core check
is the `invocation` tool_used grader: positive cases require a matching Skill call;
negative cases require no matching call. These cases do not grade dashboard quality
or setup behavior, and have no LLM behavior graders.

Cases allow only `[Skill, Read, Glob, Grep]`, with six turns and a 90-second timeout.
That read-only tool allowlist prevents setup commands and file writes; the prompts
contain only the user request, without instructions that suppress skill invocation.

Read the **plugin-fired indicator rate** in the with-plugin results: it should be
100% for should-trigger cases and 0% for should-not-trigger cases. Positive
invocation graders use `arm: with-only` and are excluded from the comparative score;
negative checks use `min: 0`, `max: 0`, and `arm: both`. The no-plugin baseline runs
automatically, but the comparative/ablation score is not the trigger-quality score.
Results stay in ignored `evals/results/`; `--no-publish` keeps the report local.
Running the eval requires Claude credentials; offline validation only checks case
configuration, not observed trigger rates.
