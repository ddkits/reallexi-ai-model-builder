# Public and Private Release Profiles

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder uses controlled source and public launcher profiles.

## Reallexi-Owned Source Profile

Reallexi LLC owns the implementation, release operations, guidelines-site
source, and customer-only or enterprise-only material. Those materials are not
distributed through the community repository.

## Public Launcher Profile

Public launcher files live at https://github.com/ddkits/reallexi-ai-model-builder. This profile ships docs,
community files, validation scripts, package access metadata, and Docker Compose
runtime references. It does not ship private source.

Model Surgery is the explicit community source exception: its approved
extension files and [guide](MODEL_SURGERY.md) ship publicly, including the
[wiki sources](wiki/Model-Surgery.md). Other runtime implementations and
private sibling plugins remain excluded.

## Public-Safe Guides

The generated public repository includes public-safe guides only:

* repository setup and install;
* private core access model;
* contribution and governance;
* extension and theme boundaries;
* training-source license review;
* personal, commercial, EU, and USA policy guidance.

Detailed operating guides, endpoint catalogs, publishing internals, worker
internals, and GitHub Pages source are intentionally excluded.
