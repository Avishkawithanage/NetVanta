# Project structure

```text
NetVanta/
├── app.py                      Entry point (launch, fatal-error handler, --smoke-test)
├── requirements.txt            Runtime dependencies
├── requirements-dev.txt        + pytest, ruff, PyInstaller, Pillow
├── pyproject.toml              Ruff and pytest configuration
├── netvanta.spec               PyInstaller recipe
├── version_info.txt            Windows file-properties for NetVanta.exe
├── build.ps1                   One-command build: tests -> exe -> installer
├── LICENSE  README.md  .gitignore
├── assets/netvanta.ico         Application icon
├── installer/NetVanta.iss      Inno Setup script (output goes to installer/Output, git-ignored)
├── tools/make_icon.py          Generates the icon
├── screenshots/                Images used by the README
├── development/                Documentation (this folder)
├── tests/                      pytest suite
└── netvanta/
    ├── __init__.py             APP_NAME, __version__
    ├── defaults.py             Default settings, numeric limits
    ├── models/results.py       Status enum, CheckResult (the one result type)
    ├── utils/
    │   ├── validation.py       Host / port / number / URL validation
    │   ├── subprocess_runner.py  Safe commands (no shell), timeouts, cancel, streaming, PowerShell+JSON
    │   ├── export.py           CSV / JSON export
    │   ├── logging_setup.py    Rotating local log
    │   └── paths.py            %APPDATA%\NetVanta paths, bundled resources
    ├── services/               All networking logic - no UI code
    │   ├── adapter_service.py  Adapters, IPs, gateways, DNS (single source of truth)
    │   ├── ip_config.py        IP Configuration view over adapter_service
    │   ├── ping_service.py     ping.exe wrapper + parser + statistics
    │   ├── dns_service.py      dnspython lookups
    │   ├── traceroute_service.py  tracert.exe streaming parser
    │   ├── arp_service.py  route_service.py  dns_cache_service.py   read-only viewers
    │   ├── tcp_check_service.py   Bounded TCP connects
    │   ├── internet_check_service.py  HTTPS checks + public IP (external)
    │   ├── diagnosis_service.py   Quick Diagnosis steps + rule engine (interpret())
    │   └── monitor_service.py     Live Monitor scheduler and state machine
    ├── data/
    │   ├── database.py         SQLite wrapper (lock + transactions)
    │   ├── repositories.py     HistoryRepository, TargetRepository (parameterised SQL)
    │   └── settings_store.py   settings.json with defaults, coercion, atomic save
    └── ui/                     CustomTkinter interface
        ├── main_window.py      Window, sidebar, view stack, shutdown
        ├── context.py          AppContext shared with views
        ├── bridge.py           UiBridge (thread -> Tk) and BackgroundTask
        ├── theme.py            Colours, fonts, Treeview style
        ├── dashboard_view.py  troubleshooting_view.py  monitor_view.py
        ├── history_view.py  settings_view.py
        ├── panels.py           The 12 troubleshooting tools (thin shells over services)
        └── widgets/            ToolPanel base class, common widgets, SortableTree
```

## Data flow

```text
Button click -> ToolPanel.read_params()  (validation.py, may raise ValidationError)
             -> BackgroundTask thread    (bridge.py)
                  -> service function    (returns CheckResult, never raises for normal failures)
             -> UiBridge queue -> Tk main thread -> badge, summary, output, history save
```

- UI code never parses command output; services do, and are unit-tested.
- Workers never touch Tk widgets; they `emit()` lines and return results through the queue.
- `CheckResult` separates `summary` / `details` (NetVanta's interpretation) from `raw` (command output).

## Where data is stored

| File | Location | Content |
|---|---|---|
| `settings.json` | `%APPDATA%\NetVanta` | User settings |
| `netvanta.db` | `%APPDATA%\NetVanta` | `history` and `targets` tables (timestamps stored as UTC ISO-8601, shown in local time) |
| `netvanta.log` | `%APPDATA%\NetVanta` | Rotating log (512 KB x 3) |

## Deviations from the original specification

- `config/defaults.py` became `netvanta/defaults.py` so it is bundled by PyInstaller as part of the package.
- Continuous ping lives only in **Live Monitor** (one canonical place) rather than also in Troubleshooting.
- Monitor events are stored as history rows with tool `Live Monitor` instead of a second events table.
- Table viewers (ARP, routes, DNS cache, adapters) render as aligned text with a filter box instead of grid widgets.
