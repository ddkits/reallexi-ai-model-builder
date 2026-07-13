# Reallexi AI Model Builder Public Package

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder is a Reallexi LLC project for preparing data, training and
evaluating models, managing run history, and using completed artifacts. This
public repository is the community launcher, public documentation, and
extension proposal surface. The application source is not distributed here.

* Guidelines: https://llm.reallexi.io
* Public repository: https://github.com/ddkits/reallexi-ai-model-builder
* Sponsor: https://github.com/sponsors/ddkits

## Quick Start

```sh
npm run setup
npm run project
```

`npm run setup` checks Node.js, Docker, Docker Compose, local configuration,
and registry authentication. `npm run project` validates the launcher before
starting the complete runtime.

Approved installers receive the runtime through controlled package systems:

* Docker/OCI images: `ghcr.io/ddkits/ai-model-builder-backend:1.0.0` and `ghcr.io/ddkits/ai-model-builder-frontend:1.0.0`
* npm/GitHub Packages: `@ddkits/ai-model-builder-core-private@1.0.0`

See [Core Access](docs/CORE_DISTRIBUTION_GITHUB.md) for authentication and
troubleshooting.

## Automatic Phased Training

Large targets can be divided into bounded, non-overlapping windows. Each
successful phase saves checkpoint evidence and a usable adapter or full model,
then starts the next configured window automatically. The UI groups internal
phase history as one logical model chain and reports progress across the total
sample target.

If the current phase is interrupted, **Continue Phase** resumes that same
window from its latest safe state. Automatic training stops at the configured
target and never extends it silently. See the detailed
[Phased Training guide](docs/PHASED_TRAINING.md).

## Hugging Face Account Workspace

The local application centralizes Hugging Face models, datasets, Spaces, and
organization namespaces in one responsive workspace. Maintainers can create and
configure repositories, control Space lifecycle and hardware, manage public
variables and write-only secrets, and use exact confirmation for permanent
deletion. Remote controls require both local admin authorization and the Hub
account's own permissions. See the public-safe
[Hugging Face workspace guide](docs/HUGGINGFACE_WORKSPACE.md).

## Why Contribute

The public repository is designed for useful work that does not require private
application source. Community contributions can improve:

* setup, troubleshooting, and model-building documentation;
* accessibility, responsive guidance, and translations;
* public dataset metadata, license review, and provenance notes;
* reproducible test and evaluation scenarios;
* extension, theme, source-catalog, and template proposals; and
* issue triage and safe synthetic examples.

Start with [CONTRIBUTING.md](CONTRIBUTING.md), keep every example public-safe,
and explain user impact plus validation evidence.

## Support The Ecosystem

Community funding supports compatibility work, documentation, validation,
accessibility, and contribution review:

* [GitHub Sponsors](https://github.com/sponsors/ddkits)
* [Buy Me a Coffee](https://buymeacoffee.com/ddkits)
* [Reallexi sponsorship](https://reallexi.com/sponsor)

Sponsorship does not transfer ownership, maintainer access, voting rights, or
release authority. See [Sponsorship](docs/SPONSORSHIP.md) for the public policy.

## Documentation

* [Documentation index](docs/README.md)
* [Contributing](CONTRIBUTING.md)
* [Public repository rules](docs/PUBLIC_REPOSITORY_GUIDE.md)
* [Extensions and themes](docs/EXTENSIONS.md)
* [Training source proposals](docs/TRAINING_DATA_SOURCES.md)
* [Model artifacts and downloads](docs/MODEL_ARTIFACTS.md)
* [Hugging Face account workspace](docs/HUGGINGFACE_WORKSPACE.md)
* [Phased and incremental training](docs/PHASED_TRAINING.md)
* [Personal and commercial policy](docs/PERSONAL_COMMERCIAL_POLICY.md)
* [Sponsorship](docs/SPONSORSHIP.md)

## Repository Boundary

This repository intentionally contains public guides, community templates,
launcher validation, and versioned runtime references only. It does not contain
application implementation, internal operations, customer data, credentials,
model artifacts, or the source for the guidelines website.

GitHub Pages must remain disabled for this repository. The public-facing
guidelines at https://llm.reallexi.io are built and deployed by Reallexi LLC
from a separately controlled source repository.

## Services

* UI: http://localhost:55173
* API: http://localhost:58080

All app ports stay in the required `54376-64322` range.
