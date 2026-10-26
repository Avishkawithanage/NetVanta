# Technology

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (built with 3.14) | Fast to develop, rich standard library for sockets/SQLite |
| GUI | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 6 | Modern look on plain Tkinter, small, no Qt/Electron weight |
| Tables | `ttk.Treeview` (styled) | Sortable, virtualised rows; CustomTkinter has no table |
| DNS | [dnspython](https://www.dnspython.org/) | Real record types, custom resolver, distinct error classes |
| Networking | `socket`, `ssl`, `urllib`, `ipaddress`, `concurrent.futures` | No extra dependencies |
| System data | Windows PowerShell (`Get-NetAdapter`, `Get-NetIPAddress`, `Get-NetRoute`, `Get-DnsClientServerAddress`, `Get-DnsClientCache`) returning JSON | Locale-independent and structured; no fragile text parsing |
| ICMP / trace / ARP | `ping.exe`, `tracert.exe`, `arp.exe` | Raw ICMP sockets need admin rights; the built-ins do not |
| Storage | SQLite (`sqlite3`), JSON settings | Local, zero-config, parameterised SQL |
| Tests | pytest (131 tests) | Mocks for subprocess/network |
| Lint | ruff | Fast, single tool |
| Packaging | PyInstaller (one-folder) + Inno Setup 6 | Standalone exe, then a conventional per-user installer |

## Design decisions

- **Read-only and safe.** No command changes system state. Every subprocess uses an argument list (never a shell) and has a timeout;
  user input is validated first (a host beginning with `-` is rejected so it can never be read as a ping flag).
- **Locale-tolerant parsing.** Ping success is a *reply line* containing `time=`/`time<` and no commas, not the English word "Reply".
  Windows data comes via PowerShell JSON, not translated text. ARP/trace parsing anchors on IPs, MACs and numbers.
- **No "false certainty".** Ping failure, timeouts and missing hops carry explanations; Quick Diagnosis findings are phrased as
  *possible*; one failing HTTPS endpoint never declares the internet down.
- **Responsive UI.** Each run is a daemon thread (`BackgroundTask`) with a cancel `Event`; results go through a queue polled by Tk every 40 ms.
  Streaming tools (`ping`, `tracert`, diagnosis) emit lines as they arrive.
- **Bounded concurrency.** Monitor: one scheduler thread + pool of 8, at most one in-flight check per target, 50 targets max.
  TCP test: 6 workers, 20 ports max.
- **State machine, not a log spammer.** A target is *down* after 2 consecutive failures and *up* after 1 success; only transitions are stored.
- **TLS note.** Python 3.13+ enables strict X.509 verification, which rejects some valid public certificates. The Internet Check
  keeps normal verification but clears `VERIFY_X509_STRICT`.
- **Privacy.** No telemetry; external calls only on explicit user action and listed in the Settings privacy note.

## Dependencies (runtime)

- `customtkinter` (pulls `darkdetect`, `packaging`)
- `dnspython`

Development only: `pytest`, `ruff`, `pyinstaller`, `pillow` (icon generation).
