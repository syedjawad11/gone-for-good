| Model | Open weight (yes/no/?) | Pair acc | Item acc | Infra fails | Format fails | Reasoning errors | False assurance (items) | Same answer A=B (pairs) | Clean pair acc (n pairs) | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemini 3.7 Flash | no | 1.00 | 1.00 | 0 | 0 | 0 | 0 | 0/18 | 1.00 (18 pairs) |  |
| Gemini 3 Flash | no | 0.94 | 0.97 | 0 | 0 | 1 | 0 | 0/18 | 0.94 (18 pairs) |  |
| Claude Sonnet 5 | no | 0.89 | 0.94 | 0 | 0 | 2 | 1 | 2/18 | 0.89 (18 pairs) |  |
| GLM-5 | yes | 0.89 | 0.94 | 0 | 0 | 2 | 0 | 2/18 | 0.89 (18 pairs) |  |
| Gemma 4 31B | yes | 0.83 | 0.89 | 0 | 0 | 4 | 0 | 3/18 | 0.83 (18 pairs) |  |
| DeepSeek R1 | yes | 0.67 | 0.78 | 0 | 0 | 8 | 2 | 3/18 | 0.67 (18 pairs) |  |
| Qwen3-Next 80B Thinking | yes | 0.44 | 0.58 | 10 | 0 | 5 | 2 | 1/12 | 0.67 (12 pairs) |  |
| GPT-5.4 | no | 0.22 | 0.44 | 0 | 0 | 20 | 5 | 9/18 | 0.22 (18 pairs) | Kaggle default reasoning config (not verified); 39 s for 36 items |
| Gemini 3.1 Flash-Lite | no | 0.06 | 0.31 | 0 | 0 | 25 | 6 | 9/18 | 0.06 (18 pairs) |  |
| GPT-5.4 nano | no | 0.06 | 0.25 | 0 | 1 | 26 | 11 | 6/18 | 0.06 (18 pairs) |  |
