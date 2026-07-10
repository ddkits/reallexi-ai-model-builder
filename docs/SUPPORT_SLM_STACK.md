# Public Support SLM and RAG Guide

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder recommends a support-agent-first stack for community and client
evaluation. This guide documents public-safe defaults, not private training
implementation details.

## Recommended Order

1. RAG first for product knowledge and support answers.
2. SLM/LLM for reasoning, wording, tool use, and chat behavior.
3. LoRA or QLoRA-style adapter training for tone, rules, and workflow.
4. Scratch training only for research experiments.

## Public Defaults

| Layer | Default |
| --- | --- |
| Main SLM | microsoft/Phi-4-mini-instruct |
| Fallback SLM | microsoft/Phi-3.5-mini-instruct |
| Local runner | Ollama phi4-mini |
| Embeddings | BAAI/bge-small-en-v1.5 |
| Multilingual embeddings | BAAI/bge-m3 |
| Database | SQLite for local tickets, docs, chunks, feedback, and evaluations |
| Training style | Adapter-first, not full model training by default |

## Sample Targets

| Stage | Clean Examples |
| --- | ---: |
| Start | 5,000 |
| Good | 10,000 |
| Production | 20,000 |
| Evaluation holdout | 1,000-2,000 |

Public datasets can bootstrap behavior, but product truth should stay in
approved local docs, tickets, FAQs, policies, and RAG knowledge sources so it can
be updated, audited, and removed.

## Public Source Ideas

* customer-support intent datasets;
* helpfulness and instruction-following datasets;
* question-answering datasets for evidence-bound responses;
* summarization datasets for ticket and conversation digests;
* safety and evaluation datasets for red-team checks.

Always review model and dataset licenses before commercial use.
