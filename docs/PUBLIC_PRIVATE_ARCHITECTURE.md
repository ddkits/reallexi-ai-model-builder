# Public and Private Repository Architecture

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder separates the community surface from the Reallexi LLC-owned
application source and release operations.

## Public Community Layer

The public repository at https://github.com/ddkits/reallexi-ai-model-builder contains:

* setup, validation, and launcher commands;
* public contribution, policy, support, and governance documents;
* extension and training-source proposal guidance;
* versioned package and container references;
* community issue and pull request templates.

It does not contain application source, internal architecture, private
operating procedures, credentials, customer data, runtime databases, model
artifacts, or release infrastructure.

## Core Access

Approved users pull versioned runtime components through access-controlled
package management:

* npm or GitHub Packages for private packages;
* OCI/Docker registries for runtime images.

For GitHub Actions in the public repo, use the automatic `GITHUB_TOKEN` only
after the package settings grant ddkits/reallexi-ai-model-builder read access. For local
machines, users authenticate directly with GitHub Packages or GHCR from their
own GitHub account; no Reallexi server should create or store GitHub package
tokens.

## Guidelines Site Ownership

GitHub Pages is disabled on the public repository. The public-facing guidelines
site at https://llm.reallexi.io is deployed from a separately controlled
Reallexi LLC repository. Its source, deployment configuration, and operating
guides are not part of this community package.

Production deployments should pin package versions, image digests, and
lockfiles.
