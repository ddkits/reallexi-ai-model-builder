# Public Extension Guide

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder supports a reviewed plugin and theme model. Public extensions
should be manifest-first and should integrate through documented extension
points rather than patching core files.

## Allowed Public Extension Types

* plugin manifests;
* static UI assets for custom plugin pages;
* separate micro-app bundles loaded through approved plugin page declarations;
* theme token overrides;
* external service integrations declared in the manifest;
* curated source catalog contributions;
* documentation and examples.

## Boundary Rules

1. Do not modify Reallexi LLC ownership notices or backlinks.
2. Do not bypass validation, licensing, admin controls, or release profiles.
3. Do not store secrets, tokens, customer data, uploaded files, or model
   artifacts inside plugin assets.
4. Do not depend on private source files or undocumented internal functions.
5. Do not publish screenshots or media that reveal private data or local paths.
6. Keep app ports inside the approved `54376-64322` range.

## Manifest Expectations

Every public plugin should declare:

* stable ID and human-readable name;
* owner, license, copyright, and description;
* extension points used;
* permissions requested;
* UI assets or external URLs if a page is added;
* theme tokens if styling is changed;
* integration notes and review instructions.

Reallexi LLC maintainers decide whether an extension remains public, moves to a
private/customer profile, or is declined.
