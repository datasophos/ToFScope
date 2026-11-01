---
name: tofscope-release
description: Use when preparing or publishing a ToFScope release, changing its package version, or drafting release notes.
---

# ToFScope releases

Prepare the release on a branch based on current `main`. Inspect the working tree, published releases, tags, and changes since the previous release. A documentation-only change does not require a package release.

## Choose the version

Review the complete changes since the previous release, including application changes bundled in documentation PRs. Propose a version using semantic versioning: patch for backward-compatible fixes, minor for backward-compatible functionality, and major for incompatible changes. For a `0.y.z` release, recognize that SemVer treats the public API as unstable; explain how the proposed increment communicates the actual changes without assuming stable-release compatibility guarantees. Check that the proposed version has not already been released or tagged.

Present the proposed version and a concise rationale to the user and ask for confirmation before proceeding. Wait for confirmation before changing versioned files or preparing the release PR. If the user chooses a different version, use that version after checking that it is available. Version confirmation is separate from the later approval to publish.

## Prepare

- Draft accurate user-facing release notes for a GitHub Release; do not claim a change was released before publication.
- Update the version in `pyproject.toml`, the ToFScope entry in `uv.lock`, `src/tofscope/__init__.py`, `frontend/package.json`, `frontend/package-lock.json`, `scripts/build_frontend.py`, `tests/test_distribution.py`, and `Dockerfile`. Search for the previous version to find any additional references; inspect matches before changing them. Confirm the lock is consistent and the version is not already tagged.
- Regenerate the API schema with `npm --prefix frontend run generate:api`, then rebuild packaged assets with `uv run python scripts/build_frontend.py`. The asset manifest records the version and a hash of frontend sources and package metadata.
- Run checks appropriate to the changes and the release. The source, browser, distribution, and container checks are described in `docs/technical-documentation/40-building-and-testing.qmd` and `.github/workflows/ci.yml`. Build fresh wheel and sdist artifacts, check their versions, and run the distribution smoke test when practical. Report checks that could not run and why.
- Save the proposed GitHub Release notes in `docs/release-notes/<version>.md`. Review and commit the release changes, push the branch, and open a **draft PR** against `main`. Include the version, notable changes, and verification results in the PR.
- Give the user the draft PR link and ask for approval to proceed with the release. Stop at this point until the user approves; do not merge, tag, or publish while approval is pending. A request to prepare a release authorizes the draft PR, not publication.

## Publish after approval

Once the user approves proceeding with the draft release PR, that approval authorizes the steps below. Resume from the existing PR and confirm its state and target commit before making changes.

1. Mark the draft PR ready for review and merge it, respecting repository requirements. Fetch `main` and identify the actual merged commit (including when GitHub squash-merges); check its `pyproject.toml` version and confirm the tag does not already exist locally or remotely.
2. Create and push an annotated `v<version>` tag on that merged commit. Pushing it triggers `.github/workflows/publish.yml`, which checks that the tag matches the package version, builds distributions, and publishes to PyPI. Do not tag an unmerged branch or retry an existing tag blindly.
3. Create the GitHub Release for that tag with the reviewed notes, for example `gh release create v<version> --title "ToFScope <version>" --notes-file docs/release-notes/<version>.md --verify-tag`. Do not use `--generate-notes` in place of the prepared notes. Great Docs generates its changelog from published GitHub Releases, not tags or these local files alone.
4. After the GitHub Release is published, dispatch `gh workflow run docs.yml --ref main`. The documentation workflow does not run on release events, so the earlier main-branch build cannot include the new release.
5. Report the PR, tag, GitHub Release, documentation dispatch, and any unverified publication status. The tag initiates publication; it is not proof that PyPI publishing succeeded.

Follow the user's authorization for external actions, and do not monitor GitHub Actions unless explicitly asked. Never modify acquisition data for release checks; use disposable copies or the distribution check's disposable data.
