# Unattended refresh regression guards

Every named case in `test_auto_refresh.py` has a behavior assertion that fails if
its corresponding logic is removed. All model/network/scheduler calls are mocked;
local git fixtures and disposable files are real.

| Case | Assertion guarding the requirement |
|---|---|
| unchanged | Four call counts equal zero; removing the fast exit calls refresh/model/build/publish. |
| failed source | Both actual runs return partial and HTML contains the missing file error; caching failures makes the second return zero. |
| shared lock | Busy manual collection/build create no manifest/page, auto probe is never called; a killed lock holder permits immediate acquisition. |
| none/cache | `assert_not_called`, three-item batch, no cached titles in prompt, one call/project, persisted hash/URL and exact week count. |
| model failure/language | Failure returns false and creates no cache; simplified-only, English-only zh-TW and CJK en output is rejected. |
| schedule | Repeated fake installs are byte-identical with one marker; changed cadence replaces it; remove preserves unrelated jobs; Windows uses `/F`, PATH and inclusive duration. |
| publish | Two equal pages make one deploy; changed page makes another; failed deploy keeps the receipt; no `--reuse`; Pages/Artifact make zero calls. |
| source fingerprints/fatal | Non-current branch, untracked count and PR updatedAt each change the fingerprint; fatal refresh creates no fingerprint file. |
| banner | Exactly three actionable command rows; escaped names; no git or fresh-source rows; zh-TW title. |
| rollover | Changing only the stored calendar day causes one collection. |
| files/render | Markdown/data modifications change file fingerprints; cached note and missing-summary banner appear in built HTML. |
| CLI contracts | Mocked argument lists require exact models, stdin, isolation, ephemeral/read-only mode, disabled Claude tools/MCP/session persistence. |
| live remote | Changing only ls-remote output changes fingerprints; any fetch or other command raises. |
