# Runtime Access Through GitHub Packages And GHCR

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder keeps application source outside the public launcher. Approved
users install versioned runtime components from GitHub Packages and GHCR.

## Runtime Components

* npm package: `@ddkits/ai-model-builder-core-private@1.0.0`
* backend image: `ghcr.io/ddkits/ai-model-builder-backend:1.0.0`
* frontend image: `ghcr.io/ddkits/ai-model-builder-frontend:1.0.0`

These identifiers are install references. They do not include application
source or internal release instructions.

## Local Installation

1. Confirm that your GitHub account has read access to the approved packages.
2. Authenticate npm when package access is required:

   ```sh
   npm login --scope=@ddkits --auth-type=legacy --registry=https://npm.pkg.github.com
   ```

3. Authenticate Docker when the runtime images are restricted:

   ```sh
   docker login ghcr.io
   ```

4. Run the environment and access checks:

   ```sh
   npm run setup
   ```

5. Validate and start the complete project:

   ```sh
   npm run project
   ```

## GitHub Actions Access

Use the workflow's automatic `GITHUB_TOKEN` with `packages: read` after a
package owner grants this public repository access. Do not commit personal
access tokens, registry passwords, or generated credentials.

## Common Access Errors

| Symptom | Resolution |
| --- | --- |
| npm returns 401 | Sign in to the GitHub Packages registry with an account that has package read access. |
| npm returns 403 or 404 | Confirm the package version and ask the package owner to grant repository or account access. |
| Docker returns denied | Sign in to GHCR and confirm image read access. |
| Startup reports a missing image | Check the configured image version in `.env`, then rerun `npm run setup`. |

GitHub Pages is not used by this repository. Public guidelines are served from
https://llm.reallexi.io through a separately controlled Reallexi LLC deployment.
