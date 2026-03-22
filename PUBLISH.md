# Publishing kioblog to PyPI

This document describes the process for building and uploading a new release of `kioblog` to [PyPI](https://pypi.org/project/kioblog/).

## Prerequisites

Install the build and upload tools (once):

```bash
pip install build twine
```

Your PyPI credentials must be configured. The recommended approach is a **token** stored in `~/.pypirc`:

```ini
[pypi]
  username = __token__
  password = pypi-<your-token-here>
```

Or pass them interactively when `twine` prompts.

---

## Release Checklist

### 1. Bump the version

Edit `setup.py` and update the `version` field following [semantic versioning](https://semver.org/):

```python
version='0.1.5',   # was 0.1.4a0
```

Also update `download_url` to point to the new tag:

```python
download_url='https://github.com/Eric-Bujeque/kioblog/archive/refs/tags/v0.1.5.tar.gz',
```

### 2. Commit and tag

```bash
git add setup.py
git commit -m "Bump version to 0.1.5"
git tag v0.1.5
git push origin django5 --tags
```

### 3. Clean previous builds

```bash
rm -rf dist/ build/ *.egg-info/
```

### 4. Build the distribution packages

```bash
python -m build
```

This produces two files inside `dist/`:
- `kioblog-X.Y.Z.tar.gz` — source distribution
- `kioblog-X.Y.Z-py3-none-any.whl` — wheel

### 5. Check the packages (optional but recommended)

```bash
twine check dist/*
```

### 6. Upload to PyPI

```bash
twine upload dist/*
```

Twine will ask for your username and password (or use `~/.pypirc` automatically).

After upload, the new version will be available via:

```bash
pip install kioblog==X.Y.Z
```

---

## Test upload (PyPI Test instance)

To do a dry run without affecting the real PyPI:

```bash
twine upload --repository testpypi dist/*
```

Check the result at https://test.pypi.org/project/kioblog/

---

## Version naming conventions used in this project

| Suffix | Meaning | Example |
|---|---|---|
| `aN` | Alpha | `0.1.4a0` |
| `bN` | Beta | `0.1.4b1` |
| `rcN` | Release candidate | `0.1.4rc1` |
| *(none)* | Stable release | `0.1.4` |
