# GitHub publishing

Research Software Tools uses a GitHub OAuth App for an explicit, user-initiated repository publish.
The user authorizes the app, chooses a personal account or organization, and creates one
repository.

(local-oauth-app)=
## Local OAuth App

An owner of the GitHub organization hosting the OAuth App registers it under **Settings →
Developer settings → OAuth Apps**. For the Compose deployment, use:

```text
Application name: LUMC Research Software Tools
Homepage URL: http://localhost:8000
Authorization callback URL: http://localhost:8000/api/github/callback
```

Copy the client ID, generate a client secret, and generate a separate cookie-encryption secret:

```bash
openssl rand -base64 48
```

Add these values to the ignored `.env` file:

```text
RS_TOOLS_PUBLIC_BASE_URL=http://localhost:8000
RS_TOOLS_GITHUB_CLIENT_ID=<OAuth App client ID>
RS_TOOLS_GITHUB_CLIENT_SECRET=<OAuth App client secret>
RS_TOOLS_GITHUB_COOKIE_SECRET=<at least 32 unpredictable bytes>
```

Recreate the application container:

```bash
docker compose up -d --force-recreate app
```

Never put either secret in chat, tickets, screenshots, or source control. The callback is always
`RS_TOOLS_PUBLIC_BASE_URL/api/github/callback`.

## Test the flow

1. Open <http://localhost:8000> using exactly the configured origin. `localhost` and `127.0.0.1`
   are different cookie hosts.
2. Create a workspace and expand **Entire repositories**.
3. Choose **Create repository on GitHub**, then **Sign in with GitHub**.
4. Review and authorize the requested scopes.
5. Confirm the owner, repository name, and visibility, then create the repository.
6. Follow the success link. The interface reports whether the OAuth grant was revoked; use
   **Disconnect GitHub** if automatic revocation failed.

The request uses these scopes:

| Scope | Purpose |
| --- | --- |
| `repo` | Create and write public or private repositories as the user |
| `workflow` | Add generated files below `.github/workflows/` |
| `read:org` | List organizations available to the user |

Organization OAuth policies, SAML authorization, visibility rules, and the user's own role can
still prevent access.

## Production OAuth App

After choosing the public HTTPS origin, update the OAuth App's homepage and callback:

```text
Homepage URL: https://rs-tools.example.org
Authorization callback URL: https://rs-tools.example.org/api/github/callback
```

Use the platform's secret manager and file-backed settings where possible:

```text
RS_TOOLS_PUBLIC_BASE_URL=https://rs-tools.example.org
RS_TOOLS_GITHUB_CLIENT_ID=<OAuth App client ID>
RS_TOOLS_GITHUB_CLIENT_SECRET_FILE=/run/secrets/rs-tools-github-client-secret
RS_TOOLS_GITHUB_COOKIE_SECRET_FILE=/run/secrets/rs-tools-github-cookie-secret
```

Do not configure an inline secret and its `_FILE` counterpart together. Ensure the reverse proxy
forwards the original HTTPS scheme and host.

## Security and failure behavior

1. The service creates encrypted OAuth state bound to the workspace and a PKCE verifier.
2. GitHub returns a temporary code and state to the callback.
3. The backend validates both and exchanges the code for a user token.
4. The token is held only in an encrypted, HttpOnly, SameSite cookie, never Redis or workspace
   data.
5. Generated output is checked before repository creation.
6. The token creates the repository, blobs, tree, commit, and branch.
7. After success, the service asks GitHub to delete the complete OAuth grant and removes the
   cookie. **Disconnect GitHub** performs the same revocation on demand.

If revocation fails, the created repository still exists and its link remains visible. The grant
can also be removed in GitHub under **Settings → Applications → Authorized OAuth Apps**.

GitHub can reject creation because of organization policy, SAML requirements, visibility rules,
permissions, or a name collision. If GitHub fails after creating the empty repository, its owner
may need to remove it manually; the service does not automatically delete external repositories.

Official references: [creating an OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app),
[authorizing OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps),
[OAuth scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps), and
[deleting an OAuth authorization](https://docs.github.com/en/rest/apps/oauth-applications#delete-an-app-authorization).
