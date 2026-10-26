# How to use this repository (developer guide)

## Requirements

- Windows 10/11
- Python 3.11 or newer (developed and tested on Python 3.14)
- Git
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) - only to build the installer (`winget install JRSoftware.InnoSetup`)

## 1. Run from source

```powershell
cd "E:\my tools\NetVanta"
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python app.py
```

`python app.py --smoke-test` builds the window, visits every view and exits (used as a launch check).

Set `NETVANTA_HOME` to a folder to keep settings/history/logs away from `%APPDATA%\NetVanta` while developing.

## 2. Run the tests and linter

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check netvanta app.py tests tools
```

Tests mock subprocesses and the network, so they do not need the internet. A few use real loopback sockets and short
child processes.

## 3. Build the Windows app and installer

One command does everything (tests -> icon -> PyInstaller -> Inno Setup):

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Results:

| Output | Path | Use |
|---|---|---|
| App folder (portable) | `dist\NetVanta\NetVanta.exe` | Copy the whole folder anywhere and run |
| **Installer** | `installer\Output\NetVanta-Setup-1.0.0.exe` | Give this one file to anyone with Windows 10/11 |

Manual steps if you prefer:

```powershell
.\.venv\Scripts\python tools\make_icon.py                 # regenerate assets\netvanta.ico
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean netvanta.spec
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\NetVanta.iss
```

### Releasing a new version

1. Change `__version__` in `netvanta/__init__.py`, `AppVersion` in `installer/NetVanta.iss`, and the versions in `version_info.txt`.
2. Run `build.ps1`.
3. Test the installer on a clean PC or VM (silent test: `NetVanta-Setup-x.y.z.exe /VERYSILENT /DIR=C:\Temp\nv`).
4. Commit, tag (`git tag v1.0.0`), push, and attach the installer to a GitHub Release.

## 4. Adding a new troubleshooting tool

1. Put the logic in `netvanta/services/<name>_service.py`; return a `CheckResult` (never touch the UI there).
2. Add unit tests in `tests/`.
3. In `netvanta/ui/panels.py` subclass `ToolPanel`: implement `build_inputs`, `read_params` (validate with
   `netvanta/utils/validation.py`) and `work`; register it in the `PANELS` list.

## 5. Git workflow used here

```powershell
git add -A
git commit -m "Describe the change"
git push origin main
```

Remote: `https://github.com/Avishkawithanage/NetVanta.git`
