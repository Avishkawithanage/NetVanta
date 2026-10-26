# Verification checklist (v1.0.0)

Recorded on Windows 10 Home 22H2, Python 3.14.3.

## Automated

| Check | Result |
|---|---|
| `pytest -q` | **123 passed** |
| `ruff check netvanta app.py tests tools` | clean |
| `python app.py --smoke-test` (all 5 views build and render) | exit code 0, empty log |
| `dist\NetVanta\NetVanta.exe --smoke-test` (PyInstaller build) | exit code 0 |
| Installer: silent install to a temp folder, launch with `--smoke-test`, silent uninstall | installed app exit 0; files removed on uninstall |

Test coverage areas: host/port/number validation, ping parsing and statistics (zero replies, no divide-by-zero), ping failure
modes (DNS, missing command, timeout, cancel), DNS outcomes (success / NXDOMAIN / no answer / timeout / resolver failure),
traceroute partial output, TCP outcomes (connected / refused / timeout / DNS), diagnosis rules (each check failing independently),
SQLite CRUD, SQL-injection inertness, settings persistence/corruption, CSV/JSON export and write failures, ARP/route/DNS-cache/adapter
parsers, internet-check classification, monitor state machine (no duplicate events), stop/rapid start-stop/shutdown, probe exceptions.

## Manual / live checks performed

- IP Configuration, ARP, routes, DNS cache, DNS lookup, TCP, traceroute and ping run against the real machine and returned real data.
- Quick Diagnosis, Cable & Link Health and Full Analysis ran end to end on a live Wi-Fi connection (the unplugged Ethernet adapter was correctly reported as no link; the cable layer was skipped in Full Analysis). Not yet tried with a real cable plugged in.
- Live Monitor: reachable hosts, an unreachable host (one FAIL event), recovery path covered by tests.
- Dashboard, History, Troubleshooting and Monitor views inspected via screenshots.

## Not verified

- Other Windows versions (11, 10 LTSC), non-English Windows, machines without internet, high-DPI scaling beyond 100-125 %.
- Corporate machines where PowerShell is restricted.

## Definition-of-done checklist

- [x] App launches without an unhandled exception
- [x] Navigation and theme are consistent
- [x] IP Configuration shows real system data
- [x] Ping shows real results
- [x] Continuous monitoring starts and stops safely
- [x] Quick Diagnosis runs real checks with evidence-based wording
- [x] DNS, traceroute, ARP, routes, DNS cache, TCP, adapters, internet tools work or explain their limits
- [x] Long tasks run off the UI thread; timeouts, errors and cancellation handled
- [x] Targets, settings and history persist
- [x] CSV/JSON exports contain the selected data
- [x] No dummy buttons or fabricated results
- [x] README, install, build and packaging instructions present
- [x] Limitations disclosed
