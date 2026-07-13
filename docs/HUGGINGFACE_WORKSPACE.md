# Hugging Face Account Workspace

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder provides one responsive, local-only workspace for the Hugging
Face resources attached to the signed-in account. It complements model training
and artifact publishing with a truthful view of remote models, datasets, Spaces,
and organization namespaces.

Core guidelines: https://llm.reallexi.io

## What The Workspace Controls

| Resource | Inventory | Lifecycle controls |
| --- | --- | --- |
| Models | ID, namespace, visibility, gating, tags, activity | Create, change visibility/gating, rename or transfer, exact-confirm delete |
| Datasets | ID, namespace, visibility, gating, tags, activity | Create, change visibility/gating, rename or transfer, exact-confirm delete |
| Spaces | ID, SDK, visibility, runtime and hardware | Create, pause, restart, factory reboot, hardware/sleep request, rename or transfer, delete |
| Space config | Public variables and secret-management capability | Set/delete variables; set/delete write-only secrets by key |

The signed-in user's namespace and reported organization namespaces are queried
independently. If one provider request fails, the interface can preserve the
rest of the inventory and show a partial error instead of hiding all resources.

## Safety Model

Hub controls require two layers: local admin authorization and a Hugging Face
token with the provider permission required by the action. The application does
not bypass organization roles, resource groups, billing, gating, quotas, or Hub
policy. Repository mutations are restricted to namespaces attached to the
authenticated account.

Token and secret values are never returned in inventory data. Space secrets are
write-only in the UI. Public Space variables remain visible by design and must
never be used for credentials. Paid Space hardware can create provider charges;
contributors should keep billing warnings clear and accessible.

Permanent repository deletion requires the full repository ID and a second
confirmation. Local training artifacts and logs remain separate from remote Hub
state, so deleting a remote repository does not rewrite training history.

## Relationship To Model Building

The training form checks access to a selected base model. The Hugging Face
workspace manages the account and remote repository lifecycle. The Trained
Models workspace verifies artifact identity and performs publication. Keeping
these responsibilities separate prevents a created repository from being
mistaken for a completed upload or a successfully trained model.

Publishing retains success and failure evidence against the training job so a
verified artifact can be retried after provider access or availability is
repaired. Hub lifecycle requests keep a separate local, token-safe audit trail.

## Contribution Opportunities

Public contributions can improve this feature without including credentials,
private repository names, or application internals. Useful proposals include:

* accessible responsive layouts for repository and Space controls;
* clearer destructive-action and paid-hardware warnings;
* synthetic test scenarios for provider errors and partial inventories;
* public documentation, translations, and troubleshooting decision trees;
* extension manifests for approved Hub workflows; and
* metadata display ideas that preserve the local-only security boundary.

Use synthetic account and repository names in issues, screenshots, fixtures,
and examples. Do not attach access tokens, secret values, private model cards,
customer prompts, billing data, or internal paths.

See [CONTRIBUTING.md](../CONTRIBUTING.md),
[SECURITY.md](../SECURITY.md), and the
[model artifact guide](MODEL_ARTIFACTS.md) before proposing changes.
