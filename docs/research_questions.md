# Research questions and hypotheses

Working title: An Explainable, Evidence-Evolution-Aware AI Framework for Multisource Criminal Investigation and Investigative Lead Prioritization.
Scope: decision support for investigative leads. The system does not identify criminals or determine guilt.

| ID | Research question | Hypothesis | Needs before it can be tested |
|---|---|---|---|
| RQ1 | Does multisource correlation improve lead prioritisation over single-source methods? | H1: Q40 beats random, communication-frequency, proximity and centrality baselines on P@K, R@K, nDCG@K | Baselines, metrics, many datasets with varied storylines |
| RQ2 | Does reliability/contradiction-aware analysis reduce the rank of misleading leads? | H2: a reliability- and contradiction-aware ranker places red herrings lower than Q40 | A Q40-R variant (Q40 currently ignores reliability), robustness scenarios A-D |
| RQ3 | Do evidence-evolution mechanisms keep findings consistent when evidence changes? | H3: EVLM flags exactly the findings that depend on changed evidence, preserves history, and rankings update correctly | Independently defined expectations (not derived from the system's own links) |
| RQ4 | Does evidence-grounded RAG improve factual accuracy and traceability of AI answers? | H4: retrieval-grounded answers have higher citation precision and fewer unsupported claims than ungrounded ones | Golden questions, real-LLM runs, adversarial validator tests |
| RQ5 | How does performance change with data scale? | H5: query, recompute, ranking and retrieval time grow acceptably from 1x to 100x | Scaled datasets, timing harness. Measurement method fixed before running |

Rules for the experiments: Q40 and its SQL are frozen at tag `research-baseline-v1`; variants are new files, never edits. No weight tuning on evaluation data. All results come from scripts under `research/` and are written to `research/results/`.
