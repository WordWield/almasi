# Almasi

Install the loader once in a Python 3.11+ environment with Git and pip available:

```sh
pip install almasi
```

```python
from almasi import a, o
```

The loader owns acquisition only. Core architecture primitives live in [almasi.a](https://github.com/WordWield/almasi.a); every library follows the same acquisition contract.

On first access in a process, a missing repository is cloned; an existing Git checkout is fast-forwarded when possible. Its requirements are installed in the active Python environment, and its entry point executes under `almasi.<name>`. Repeated imports reuse the same identity. A failed update uses the local checkout, but a failed initial clone, dependency installation or import is an error.

- `ALMASI_PATH`: checkout parent (default `~/.cache/almasi/libraries`).
- `ALMASI_GIT_BASE`: trusted Git origin base (default `https://github.com/WordWield`).
- `from almasi import Libraries`: `get_path(name)`, `get_url(name)`, `is_cloned(name)`, `clone(name)`, `imp(name)`; names are public snake_case. `imp` returns the canonical published object.
- `from almasi import Git`: `clone(url, directory, timeout=None)` returns the checkout path; `pull(directory, timeout=None)` performs a fast-forward update; `is_repository(directory)` checks a checkout root. Git failures retain their native exceptions.

A repository named `almasi.<name>` provides `<name>.py` or `almasi/<name>.py` and optionally `requirements.txt`. Local directories without Git metadata are not updated. Libraries may publish their own runtime object in `sys.modules`.

Acquisition executes trusted Git code and installs dependencies. It is not a sandbox or a pinned release resolver. The current policy follows the checkout's upstream branch; use a local source tree for a fixed revision. Updates do not reload an already imported library. Cross-process checkout updates are not transactional.

Migrating from 0.1.x: reinstall the loader once, then use `from almasi import a` and `a.extend(...)` instead of `import almasi` and `almasi.extend(...)`. Architecture services now belong to `a`; acquisition and Git operations belong to the loader.
