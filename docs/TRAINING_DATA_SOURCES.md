# Public Training Source Guide

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Public source contributions should improve dataset discovery without exposing
private loaders, training internals, or customer data.

## Web, News, And Feed Collection

The application exposes a one-click **Select Web + News + Feeds** collection.
It combines versioned FineWeb/FineWeb-Edu, C4 news-like text, Wikipedia,
historical news corpora, academic papers, biomedical QA, legislation, and
government reports with bounded official NASA, JPL, SEC, and arXiv RSS/Atom
snapshots.

This is intentionally broad, but it cannot mean every page on every website.
Private, paywalled, disallowed, copyrighted, deleted, and unsafe pages are not
automatically scraped. Every catalog entry carries a review URL, provenance,
subject tags, sample cap, freshness type, and license policy. Live feeds are
HTTPS-only, bounded, protected from private-network access, and captured once
per chain so changing feed order cannot duplicate later phases. Current facts
usually belong in RAG rather than permanent model weights.

## Source Categories

AI Model Builder tracks source metadata for categories such as support, chat,
RAG and QA, code, reasoning, safety, summarization, finance, multilingual,
legal, healthcare, vision captions, and language modeling.

## Required Metadata

Every proposed source should include:

* stable source ID;
* provider and public review URL;
* source type such as hosted dataset, direct URL, or local user upload;
* modality and agent-type tags;
* license name and license policy;
* suggested sample cap;
* notes about quality, safety, and commercial review.

Prefer datasets that expose normal splits or direct data files. Legacy
script-only datasets should not be proposed for the default catalog unless the
current runtime can load them without remote-code or deprecated-script support.

When a selected optional source is unavailable, gated, removed, or incompatible,
AI Model Builder records it as skipped and continues with the sources that
loaded. Strict all-or-nothing validation belongs in private release testing.

Use the maintained namespace and a split shown by the current dataset card.
Examples include `rajpurkar/squad`, `Yelp/yelp_review_full`,
`fancyzhx/amazon_polarity`, and UltraChat's `train_sft` split. Source metadata
corrections are valuable public contributions and should include the upstream
dataset link used for verification.

## License Policies

* `permissive`: usually suitable for commercial review, but still verify.
* `attribution`: attribution is required.
* `sharealike`: derivative or redistributed outputs may have obligations.
* `noncommercial`: not for commercial or enterprise training.
* `review`: provenance, synthetic-output terms, or mixture license needs
  manual review.

## Public Data Safety

Public source proposals must not contain customer documents, support tickets,
private prompts, access tokens, downloaded datasets, or model artifacts. Use
metadata and public review links only.
