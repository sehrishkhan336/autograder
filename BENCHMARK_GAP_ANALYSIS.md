# Benchmark Gap Analysis

Source files:
- `benchmark_truth.csv`
- `benchmark_three_way_results.csv`

## Current Benchmark Metrics

Benchmark size: 15 submissions

| Metric | Result |
| --- | ---: |
| AI exact match | 4 / 15 (26.7%) |
| Python exact match | 5 / 15 (33.3%) |
| AI within-one | 10 / 15 (66.7%) |
| Python within-one | 12 / 15 (80.0%) |
| AI false passes | 0 |
| AI false rejects | 1 |
| Python false passes | 3 |
| Python false rejects | 4 |

False pass means manual grade is below 3 while the grader grade is 3 or higher.
False reject means manual grade is 3 or higher while the grader grade is below 3.

## Per-HWID Gap Table

| HWID | Manual grade | AI grade | Python grade | AI delta | Python delta | Failure type | Suspected root cause |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 376954 | 5 | 3 | 5 | -2 | 0 | AI undergrade | AI prompt appears too conservative on complete high-scoring work. |
| 376955 | 2 | 1 | 5 | -1 | +3 | Python false pass / overgrade | Scope-counting edge case; Python likely credits structure or count signals too heavily. |
| 376956 | 4 | 3 | 5 | -1 | +1 | AI undergrade / Python overgrade | Borderline severity calibration around minor rubric misses. |
| 376957 | 5 | 3 | 5 | -2 | 0 | AI undergrade | AI prompt appears too reluctant to award 5 for complete submissions. |
| 376958 | 4 | 3 | 5 | -1 | +1 | AI undergrade / Python overgrade | AI and Python bracket the manual grade; likely 4-vs-3/5 calibration issue. |
| 376959 | 4 | 1 | 1 | -3 | -3 | Shared false reject | Known `__MACOSX` false-reject case; valid submission content is likely being missed or discounted. |
| 376960 | 1 | 1 | 1 | 0 | 0 | Aligned | No observed gap. |
| 376961 | 1 | 1 | 1 | 0 | 0 | Aligned | No observed gap. |
| 376962 | 5 | 3 | 4 | -2 | -1 | Shared undergrade | Both graders are conservative on a high-scoring submission; AI penalty is stronger. |
| 376963 | 4 | 5 | 4 | +1 | 0 | AI overgrade | AI likely treats near-complete work as fully complete. |
| 376964 | 2 | 1 | 3 | -1 | +1 | Python false pass / overgrade | Python pass threshold is too lenient for a low manual-grade submission. |
| 376965 | 3 | 5 | 2 | +2 | -1 | AI overgrade / Python false reject | Borderline passing work is split: AI overcredits, Python rejects. |
| 376966 | 1 | 1 | 3 | 0 | +2 | Python false pass / overgrade | Python likely accepts superficial structural signals despite low manual quality. |
| 376967 | 5 | 5 | 2 | 0 | -3 | Python false reject / undergrade | Known Bug 3 false-reject case still appears misaligned in this run. |
| 376968 | 3 | 3 | 2 | 0 | -1 | Python false reject / undergrade | Python is too strict at the pass threshold for a manual 3. |

## Grouped Failures

### AI overgrades

- 376963: manual 4, AI 5, Python 4
- 376965: manual 3, AI 5, Python 2

### AI undergrades

- 376954: manual 5, AI 3, Python 5
- 376955: manual 2, AI 1, Python 5
- 376956: manual 4, AI 3, Python 5
- 376957: manual 5, AI 3, Python 5
- 376958: manual 4, AI 3, Python 5
- 376959: manual 4, AI 1, Python 1
- 376962: manual 5, AI 3, Python 4
- 376964: manual 2, AI 1, Python 3

### Python overgrades

- 376955: manual 2, Python 5, AI 1
- 376956: manual 4, Python 5, AI 3
- 376958: manual 4, Python 5, AI 3
- 376964: manual 2, Python 3, AI 1
- 376966: manual 1, Python 3, AI 1

### Python undergrades

- 376959: manual 4, Python 1, AI 1
- 376962: manual 5, Python 4, AI 3
- 376965: manual 3, Python 2, AI 5
- 376967: manual 5, Python 2, AI 5
- 376968: manual 3, Python 2, AI 3

### Shared failures

- 376956: both graders miss exact grade within one point in opposite directions.
- 376958: both graders miss exact grade within one point in opposite directions.
- 376959: both graders false-reject a manual 4.
- 376962: both graders undergrade a manual 5.
- 376965: both graders miss exact grade in opposite directions; Python also false-rejects.

## Recommended Next ONE Python Logic Fix

Fix the Python false-reject path for submissions whose valid content is missed during archive/file discovery, starting with HWID 376959 and the known `__MACOSX` case.

Reason: this is the clearest shared failure and a high-severity Python miss: manual 4, AI 1, Python 1. It likely affects content discovery before rubric scoring, so fixing it may convert a catastrophic false reject into a normal scoring case without changing database writes or production behavior in this calibration pass.

## Recommended Next ONE AI Prompt Calibration

Calibrate the AI prompt to award 4-5 when the required work is substantively complete and remaining issues are minor, instead of defaulting strong submissions to 3.

Reason: the dominant AI pattern is undergrading high manual grades: 376954, 376957, and 376962 are manual 5s graded as AI 3, and 376956/376958 are manual 4s graded as AI 3. The prompt should distinguish "minor issue in otherwise complete work" from "borderline pass."
