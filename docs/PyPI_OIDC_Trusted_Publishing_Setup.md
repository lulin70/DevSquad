# PyPI OIDC Trusted Publishing Setup

> **Purpose**: Configure PyPI Trusted Publishing (OIDC) for the `devsquad` package so
> `.github/workflows/release.yml` publishes to PyPI on `v*` tag push **without** storing a
> long-lived `PYPI_API_TOKEN` secret.
>
> **Repository**: `lulin70/DevSquad`
> **PyPI project**: `devsquad`
> **Workflow**: `.github/workflows/release.yml` (job: `publish-pypi`, environment: `pypi`)
>
> Related: [`docs/PYPI_TRUSTED_PUBLISHER_SETUP.md`](./PYPI_TRUSTED_PUBLISHER_SETUP.md)
> (earlier Chinese-language guide).

---

## 1. What is OIDC Trusted Publishing and why is it more secure?

PyPI Trusted Publishing uses **OpenID Connect (OIDC)** to let GitHub Actions publish to PyPI
**without any stored API token**. Instead, PyPI verifies the workflow's identity through a
short-lived OIDC token issued by GitHub on each run.

**How it works**:
1. The `publish-pypi` job runs with `permissions: id-token: write`.
2. The `pypa/gh-action-pypi-publish@release/v1` action requests a signed OIDC token from GitHub.
3. The action presents that token to PyPI.
4. PyPI checks the token's claims (`repository`, `workflow_ref`, `environment`) against a
   registered "Trusted Publisher" and, if they match, accepts the upload.

**Why it is more secure than API tokens**:
- **No secret to leak or rotate.** There is no `PYPI_API_TOKEN` in the GitHub secret store, so
  it cannot be exfiltrated, accidentally logged, or forgotten during rotation.
- **Per-workflow scoping.** Publishing is bound to a specific repository, workflow file,
  environment, and (optionally) branch/tag. A token stolen from another workflow cannot be used.
- **Per-run, short-lived credentials.** The OIDC token expires within minutes and is only valid
  for the single run that requested it.
- **Least privilege.** The job-level `permissions: id-token: write` grant is the only thing
  needed; no broad `repo`-scoped token is involved.

**Trade-off**: PyPI must have a matching Trusted Publisher registered *before* the first OIDC
publish. If the publisher is misconfigured, publishing fails. A rollback path is provided in
[Section 5](#5-rollback-plan-if-oidc-publishing-fails).

---

## 2. Configure PyPI Trusted Publishing (step-by-step)

### 2.1 Prerequisites
1. You are an **admin** of the GitHub repo `lulin70/DevSquad`.
2. You have a PyPI account and are an **Owner** or **Maintainer** of the `devsquad` project on
   PyPI (https://pypi.org/project/devsquad/).
3. `.github/workflows/release.yml` `publish-pypi` job already sets
   `permissions: id-token: write` and `environment: pypi` (verified — already in place).

### 2.2 Add a Pending Publisher on PyPI

1. Go to **https://pypi.org/manage/account/publishing/**
2. Under **"Add a new pending publisher"** (for a project that does not yet exist) — or under
   the `devsquad` project's **"Publishing"** tab if it already exists — fill in:

   | Field | Value | Notes |
   |-------|-------|-------|
   | **PyPI Project Name** | `devsquad` | Must match `name` in `pyproject.toml` |
   | **Owner** | `lulin70` | GitHub user/org owner (case-sensitive) |
   | **Repository name** | `DevSquad` | Case-sensitive — must match GitHub exactly |
   | **Workflow name** | `release.yml` | The workflow filename under `.github/workflows/` |
   | **Environment name** | `pypi` | Must match `environment: pypi` in the workflow |

3. Click **"Add"**. PyPI creates a pending publisher entry. The configuration takes effect
   immediately; the first matching OIDC publish will create/fill the project.

> **Case sensitivity matters.** `DevSquad` ≠ `devsquad`. The repository name is `DevSquad`
> (capital D and S); the PyPI project name is `devsquad` (all lowercase). Mismatched case is
> the most common cause of `invalid-publisher` errors.

### 2.3 Configure the `pypi` GitHub Environment protection (recommended)

To prevent an unauthorized or accidental tag from publishing, protect the `pypi` environment:

1. Go to **https://github.com/lulin70/DevSquad/settings/environments**
2. Click **"New environment"**, name it `pypi`, click **"Configure environment"**.
3. Enable **"Required reviewers"** and add at least one reviewer.
4. (Optional) Under **"Deployment branches and tags"**, restrict to tag pattern `v*`.
5. Save.

> If the `pypi` environment does not exist yet, the first release run will auto-create it
> *without* protection rules. Pre-create it to get protection from the first publish.

---

## 3. GitHub Actions workflow changes

The change is **additive** and keeps a fallback. In `.github/workflows/release.yml`, the
`publish-pypi` job:

- Keeps `environment: pypi` (already present).
- Keeps job-level `permissions: id-token: write` (already present — least-privilege, job-level
  not workflow-level).
- Still uses `pypa/gh-action-pypi-publish@release/v1`.
- **No longer passes `password: ${{ secrets.PYPI_API_TOKEN }}`.** When no `password` input is
  given, the action authenticates via OIDC automatically.
- The old `password` line is kept as a **commented fallback** so the team can revert in one
  edit if OIDC ever fails.

Relevant excerpt:

```yaml
  publish-pypi:
    name: Publish to PyPI
    runs-on: ubuntu-latest
    needs: build
    timeout-minutes: 15
    environment: pypi            # requires manual approval in GitHub env protection
    permissions:
      id-token: write            # required for PyPI OIDC trusted publishing
    steps:
      # ... checkout, setup-python, download-artifact ...

      - name: Publish to PyPI (OIDC Trusted Publishing)
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          # password: ${{ secrets.PYPI_API_TOKEN }}  # OIDC fallback (legacy)
          skip-existing: true    # idempotent: skip if version already exists on PyPI
```

> **Important**: do NOT set `password` to the literal string `__token__`. With this action,
> OIDC is activated by *omitting* `password` entirely. Setting `password: __token__` would
> pass the literal string as a credential and fail. The `__token__` username convention only
> applies when you call `twine upload` directly with an API token.

### 3.1 pyproject.toml

No changes are required. There is no `[tool.semantic_release]` section in `pyproject.toml`,
and Trusted Publishing needs no `pyproject.toml` metadata — all binding happens on the PyPI
side (Section 2.2). The project name (`devsquad`) and version (`4.1.0`) are unchanged.

---

## 4. How to verify the setup works

### 4.1 Pre-flight (no publish)
- Confirm the `publish-pypi` job in `.github/workflows/release.yml` contains:
  - `environment: pypi`
  - `permissions:` → `id-token: write`
  - `uses: pypa/gh-action-pypi-publish@release/v1`
  - **no active `password:` line** (it should be commented out).
- Confirm the PyPI Trusted Publisher entry matches the table in [2.2](#22-add-a-pending-publisher-on-pypi).
- Run the version-consistency check locally:
  ```bash
  python scripts/check_version_consistency.py --strict
  ```

### 4.2 Trigger a release
```bash
# After bumping/syncing the version everywhere:
git tag -a v4.1.0 -m "Release DevSquad v4.1.0"
git push origin v4.1.0
```
If `v4.1.0` already exists on PyPI and you need to re-test the pipeline, use a post-release:
```bash
git tag -a v4.1.0.post1 -m "Post-release v4.1.0.post1"
git push origin v4.1.0.post1
```

### 4.3 Watch the run
1. Open **https://github.com/lulin70/DevSquad/actions** and find the **Release** run.
2. `build` should go green.
3. `publish-pypi` will pause at the `pypi` environment for reviewer approval (if configured).
4. After approval, the upload step should succeed. On the PyPI publisher page the entry moves
   from "pending" to an active publisher.
5. **Failure signatures**:
   - `invalid-publisher` → PyPI got a valid OIDC token but no matching publisher. Re-check
     Owner/Repository/Workflow/Environment spelling and case (Section 2.2).
   - `missing or insufficient OIDC token permissions` → `id-token: write` missing or
     overridden at workflow level. Keep it job-level only.

### 4.4 Confirm the package is installable
```bash
pip install --no-deps "devsquad==4.1.0" --target /tmp/verify_install
python -c "import sys; sys.path.insert(0,'/tmp/verify_install'); from scripts.collaboration._version import __version__; print(__version__)"
# Expected: 4.1.0
```
(The workflow's `Verify PyPI publication` step already does this automatically.)

### 4.5 Remove the legacy token (after OIDC is proven)
Once two consecutive OIDC publishes succeed:
1. Delete the `PYPI_API_TOKEN` secret at
   https://github.com/lulin70/DevSquad/settings/secrets/actions.
2. Revoke the corresponding API token at https://pypi.org/manage/account/token/.
3. Delete the commented `# password: ...` line from the workflow.

---

## 5. Rollback plan if OIDC publishing fails

If an OIDC publish fails and you need to ship immediately:

1. **Re-enable API-token auth** in `.github/workflows/release.yml`, in the `publish-pypi` job:
   ```yaml
         uses: pypa/gh-action-pypi-publish@release/v1
         with:
           password: ${{ secrets.PYPI_API_TOKEN }}   # uncomment this line
           skip-existing: true
   ```
   Providing `password` makes the action use the token instead of OIDC for that run.
2. **Ensure the `PYPI_API_TOKEN` secret still exists** at
   `https://github.com/lulin70/DevSquad/settings/secrets/actions` (do not delete it until OIDC
   is proven — see 4.5). The secret should hold a valid PyPI API token (scoped to the
   `devsquad` project).
3. **Commit and push** the workflow change to the default branch.
4. **Re-run the failed release**:
   - If the `v*` tag already exists and the version is not yet on PyPI, re-run the failed
     `publish-pypi` job from the Actions UI (it will pick up the new workflow on re-run only if
     you re-run against the updated default branch; otherwise create a `vX.Y.Z.post1` tag).
   - If the version *is* already on PyPI, the `skip-existing: true` option will make the run
     a no-op; create a post-release tag instead.
5. **File an issue** with the OIDC error (`invalid-publisher`, etc.) so the root cause is
   fixed and OIDC re-enabled per Section 3.

### Rollback safety notes
- The `build` and `github-release` jobs are unaffected by the auth method; only the upload
  step changes.
- `skip-existing: true` prevents duplicate-upload errors during rollback retries.
- The `pypi` environment's required reviewers still apply during rollback, so a human still
  approves the publish.

---

## 6. Related files
- [`.github/workflows/release.yml`](../.github/workflows/release.yml)
- [`pyproject.toml`](../pyproject.toml)
- [`scripts/check_version_consistency.py`](../scripts/check_version_consistency.py)
- [`docs/PYPI_TRUSTED_PUBLISHER_SETUP.md`](./PYPI_TRUSTED_PUBLISHER_SETUP.md) (earlier
  Chinese-language guide)
