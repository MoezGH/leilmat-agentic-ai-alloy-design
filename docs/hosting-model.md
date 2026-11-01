# One codebase, two ways to run it

LeilMat is open source and also runs as a free online service. Both come from **this repository**.
The online service is not a different product or a private fork: it is this code, configured.

| | Self-hosted (default) | The free online version |
|---|---|---|
| Accounts and sign-in | Off. Nobody signs in. | On (a Supabase project and a separate account service) |
| Credits and billing | Off. | On for the features that cost money |
| AI chat and interpretation | Your own provider key, or off | The operator's key, behind sign-in and credits |
| Cloud simulations | Off unless you set a Daytona key | On, behind sign-in and credits |
| Trained models | You train them (`python -m apps.api.ml.training`) | The operator's own trained copies |
| Everything scientific | Identical | Identical |

Everything in the second column is switched on by environment variables listed in
[the configuration reference](reference/configuration.md). Nothing in the code names the online
service's host, and anything that would carry a user's token (billing, the account link) has **no
default address**, so a build you make yourself never sends a token anywhere you did not choose.

## What lives outside this repository

The operator of the online service keeps a small private repository with what only that deployment
needs: the production compose file and reverse-proxy labels, the environment values, TLS and domain
settings, and the runbook. It is deliberately not part of the project: with it you would still need
to supply your own accounts, keys and domain.

## How a release reaches the online service

1. Work happens on `main` through pull requests. CI runs the API tests, the web tests, the contrast
   check and a web build with no environment (`.github/workflows/ci.yml`).
2. The maintainer tags a release (`v0.1.0`). `.github/workflows/release.yml` builds and publishes
   the API and web images to the GitHub container registry and creates the GitHub release.
3. The operator deploys **that tag**, never an arbitrary commit. To roll back, deploy the previous
   tag. `/health` reports the running version.

**Why the web image on the registry is not what the online service runs.** Next.js writes the
`NEXT_PUBLIC_*` settings into the compiled page, so the published web image is the generic one
(accounts and billing off). The operator builds the web image from the same tag with their own
build arguments. The API has no such restriction and can be pulled as published.

## Rules that keep the line clean

- No hostnames, keys or project identifiers of the online service in the repository. Use settings.
- A hosted-only behaviour must be off unless its setting is present, and tested that way.
- Workflows that deploy are triggered by tags only, and secrets are never available to pull requests
  from forks. Changes to `.github/`, the Dockerfiles and the compose files need the maintainer's review
  (`.github/CODEOWNERS`).
- Trained models are not committed (a pickle runs code when it is loaded), and neither are data files whose
  terms do not allow redistribution; see [NOTICE.md](../NOTICE.md).
- The names and logos are not covered by the MIT licence: see [TRADEMARKS.md](../TRADEMARKS.md).
