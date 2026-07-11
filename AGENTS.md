# Public Agent Guide

Copyright (c) 2026 Reallexi LLC. All rights reserved.

This guide is for coding agents and contributors working inside the generated
public AI Model Builder launcher repository.

## Public Boundaries

* Keep Reallexi LLC ownership, copyright, package identity, and backlink.
* Do not add application source or GitHub Pages source and workflows.
* Do not document internal operations, private implementation details,
  customer data, credentials, local databases, uploads, or model artifacts.
* Prefer documentation, examples, issue templates, plugin manifests, theme
  tokens, and source metadata proposals.
* Keep app ports inside `54376-64322`.

## Required Checks

```sh
npm run setup
npm run validate
npm run project
```

## Useful Public Files

* `README.md`: install and repository overview.
* `docs/README.md`: public documentation index.
* `docs/PUBLIC_REPOSITORY_GUIDE.md`: public-safe repository rules.
* `docs/CORE_DISTRIBUTION_GITHUB.md`: package and registry access.
* `docs/EXTENSIONS.md`: plugin and theme contribution boundary.
* `docs/PLUGIN_HOOKS.md`: public hook categories.
* `docs/SUPPORT_SLM_STACK.md`: public SLM and RAG defaults.
* `docs/MODEL_ARTIFACTS.md`: public artifact identity and download guide.
* `docs/TRAINING_DATA_SOURCES.md`: public source metadata contribution guide.
* `reallexi.public.json`: generated public access manifest.
