# Development

Contributing to chordgen, working on the codebase, or building the
docs site locally.

## Clone the repo

```sh
git clone https://github.com/dlip/chordgen.git
cd chordgen
```

## Environment

### Nix

- Install [Nix](https://nixos.org/download/) or use NixOS.
- Add `devenv` to your packages.
- Run `devenv shell` or use the
  [shell hook](https://devenv.sh/auto-activation/).

### Non-nix

- Install [Python 3.11.14](https://www.python.org/downloads/release/python-31114/).
- Install `uv`:

  ```sh
  pip install uv
  ```

## Running

```sh
uv run chordgen --help
```

## Tests

```sh
uv sync --extra dev
uv run pytest
```

## Docs

The site is built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/):

```sh
uv sync --extra docs
uv run mkdocs serve     # live preview at http://localhost:8000
uv run mkdocs build     # build to ./site
```

The site is published to GitHub Pages from the `main` branch via
[`.github/workflows/docs.yml`](https://github.com/dlip/chordgen/blob/main/.github/workflows/docs.yml).

## Regenerating the config schema

`docs/schema.md` is auto-generated from the pydantic models in
`src/chordgen/config.py`. Whenever you add or change a config knob:

```sh
uv run chordgen schema
```

Commit the regenerated `docs/schema.md` alongside your code change.
