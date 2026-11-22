# Releasing

Only the owner releases. Agents never create a tag, a GitHub release or a package; `gh release create` is denied in `.claude/settings.json`.

A release here is a Git tag on `main`. The application is run from source (`python -m sheet_history`); nothing is built, packaged or published, and there is no package manifest.

## Steps

1. Check that every pull request intended for the release is merged and that CI is green on `main` (Linux and Windows, Python 3.12 and 3.13).
2. On a clean checkout of `main`, run `python -m unittest discover -s tests -t .` and confirm `OK` with no fewer tests than the last release.
3. In `CHANGELOG.md`, rename `Unreleased` to the new version and date, and add a fresh empty `Unreleased` section.
4. Set `__version__` in `sheet_history/__init__.py` to the new version. If the release changes the database schema, check that `SCHEMA_VERSION` in `sheet_history/storage.py` and the health response match `docs/architecture.md`.
5. Commit these changes through a pull request and merge it.
6. Tag the merge commit `vX.Y.Z` and push the tag. Optionally create a GitHub release from the tag with the changelog section as its notes.
