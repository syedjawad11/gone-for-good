# Frozen held-out set (Fri 9 Oct 2026)

18 pairs / 36 items: FS-5..10, DB-5..10, R-5..10. Gold generated in Docker (harness/run_in_docker.sh).
Run settings: max_tokens 16384, client timeout 600 s, one sample per item, task tasks/gone_for_good.py.
Audits before freeze: red team gpt-6.1-sol + gpt-5.5 (.agent/reviews/20261009-200245-*), blind gpt-5.5 35/36 (.agent/reviews/blind-v2/).
Do not edit anything listed below after this commit; any change means a new freeze and is disclosed in the post.

```
8c4ccb0efc257d14bf4fa74a25a5302d647d6be78aa7d540e06fa8171e447b1b  data/heldout/items.jsonl
29153d52a39606956d22631c8d78303c0d8f7ce1d83ef0e15bb268d0113c5798  data/heldout/gold.jsonl
30520633e69d887903bae27b6fd8d9064a70717f8cb5b2267bb74a5a543add5c  scoring.py
0cb6f24ec5647c7f2e91fcbee0d7478cffaca2341a1edc429c55efff38bb4cef  harness/render.py
f7092e737e1644f5603256d73854c52daf4bdbfce664c3322af14890ed44270d  tasks/build_task.py
b732d4de725728d45f35132b758c2effb83a020ee309a4515fa74f079c5795ac  tasks/gone_for_good.py
```
