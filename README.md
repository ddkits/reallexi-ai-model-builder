# Reallexi AI Model Builder Public Package

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder is a Reallexi LLC project for preparing data, training and
evaluating models, managing run history, and using completed artifacts. This
public repository is the community launcher, public documentation, and
extension proposal surface. The application source is not distributed here.

* Guidelines: https://llm.reallexi.io
* Public repository: https://github.com/ddkits/reallexi-ai-model-builder
* Sponsor: https://github.com/sponsors/Reallexi

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

## Documentation

* [Documentation index](docs/README.md)
* [Contributing](CONTRIBUTING.md)
* [Public repository rules](docs/PUBLIC_REPOSITORY_GUIDE.md)
* [Extensions and themes](docs/EXTENSIONS.md)
* [Training source proposals](docs/TRAINING_DATA_SOURCES.md)
* [Personal and commercial policy](docs/PERSONAL_COMMERCIAL_POLICY.md)

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
