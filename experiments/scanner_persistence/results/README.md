# Persistence after a self-initiated rescan

Live continuations

| Source shift | Repeat receipt | Replays | Immediate rescan | Any subsequent rescan | Invalid decisions |
|---|---:|---:|---:|---:|---:|
| 1 | +0 | 12 | 0 | 0 | 6 |
| 1 | +1 | 12 | 9 | 9 | 3 |
| 13 | +0 | 12 | 0 | 0 | 0 |
| 13 | +1 | 12 | 12 | 12 | 0 |

Immediate rescans increased by 75 percentage points in shift 1 and 100 in shift 13. Three of 48 first decisions (6.25%) hit the completion limit with empty visible text. All three were in the shift 1 positive-credit condition. Six additional responses hit the limit on the last move in shift 1's zero-credit condition. Secondary outcomes count only observed actions. The preset transfer-testing criterion was met. Eight of twelve positive-credit shift 1 replays spent all three remaining moves scanning A. All twelve zero-credit replays immediately advanced to B.

These 48 replays come from two previously observed histories. The experiment estimates response to a known payoff in this setting, not spontaneous discovery or rule-breaking. The 90 calls used 15,600 input tokens (12,570 cached) and 33,548 output tokens, for an estimated $0.344 at the previously verified Fireworks rates.

[Raw continuations](scanner.jsonl) · [Completed workflow](https://github.com/Enkrypt7/ai-sandbox-experiments/actions/runs/42720353003)
