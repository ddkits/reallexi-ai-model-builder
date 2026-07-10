# Public Plugin Hook Contract

Copyright (c) 2026 Reallexi LLC. All rights reserved.

This public contract describes safe extension categories without exposing
private implementation functions or internal admin flows.

## Public Hook Categories

| Category | Purpose |
| --- | --- |
| Navigation | Add approved plugin pages or links. |
| Dashboard Widgets | Add manifest-rendered cards. |
| Settings Panels | Add reviewed settings surfaces. |
| Training Sources | Contribute source metadata for review. |
| Job Lifecycle | Attach public-safe status, reports, or external links. |
| Prompt Processing | Declare external pre/post processing integrations. |
| Theme Tokens | Apply approved visual token overrides. |

## Integration Modes

* `declarative`: manifest data rendered by the runtime.
* `static-ui`: HTML, CSS, JavaScript, and media declared as plugin assets.
* `micro-app`: a separate UI bundle or external URL.
* `external-service`: a plugin-owned service called through reviewed
  configuration.
* `reviewed-code`: private or maintainer-reviewed code distributed only
  through an approved profile.

## Public Review Checklist

1. The manifest declares every page, asset, permission, and integration.
2. Static files stay inside the plugin package.
3. Media uses synthetic public-safe content.
4. No private source paths, tokens, admin endpoints, customer data, or model
   artifacts are included.
5. Any code execution beyond static UI is explicitly reviewed by maintainers.

Internal handler names, admin-only endpoints, and runtime implementation details
are intentionally not documented in the generated public repository.
