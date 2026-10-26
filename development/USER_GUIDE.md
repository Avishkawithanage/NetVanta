# NetVanta User Guide

NetVanta helps you find out *why* a network is misbehaving. You can run any tool by hand, or let
**Quick Diagnosis** run a series of checks and explain what the evidence suggests.

## 1. Installing

Run `NetVanta-Setup-1.0.0.exe`. It installs for your Windows account (no admin password needed), adds a Start-menu
entry and optionally a desktop shortcut. Uninstall from *Settings > Apps*.

## 2. The window

- **Sidebar** - Dashboard, Troubleshooting, Live Monitor, History & Reports, Settings / About. `Ctrl+1` ... `Ctrl+5` jump between them.
- **Status badges** always have a word and a symbol, never colour alone:
  `PASS`, `FAIL`, `WARNING`, `SKIPPED`, `UNKNOWN`.
- Long checks run in the background; the window stays usable and most tools have a **Stop** button.

## 3. Dashboard

Shows the active connection (adapter, IPv4, subnet, gateway, DNS), whether the gateway answers ping, the number of
monitored targets and the latest monitor events. Unknown values read **Unknown** - nothing is guessed.
**Check internet now** is the only dashboard action that contacts the internet.

## 4. Troubleshooting tools

Pick a tool in the list. Every tool has the same layout: inputs, **Run**, **Stop**, **Clear**, a result badge with a one-line
summary, the output, and **Copy summary**, **Export CSV / JSON...**, **Show raw output** at the bottom.

| Tool | How to use it |
|---|---|
| **IP Configuration** | Press *Check IP Configuration*. The primary connection is marked `* PRIMARY`. A `169.254.x.x` address means DHCP failed. |
| **Ping** | Enter a host or IP, packets/timeout/interval, press *Start Ping*. Results appear live. *No reply* can also mean ICMP is blocked. |
| **Quick Diagnosis** | Optionally enter a target, press *Run Quick Diagnosis* (10-25 s). Read the CHECKS first, then the FINDINGS and their *Next step*. Steps marked *(external)* contact the internet. |
| **DNS Lookup** | Enter a name, choose A/AAAA/MX/NS/TXT/CNAME, optionally a DNS server such as `1.1.1.1`. Leave the server empty for the system default. |
| **Traceroute** | Enter a target. `*` hops are common; they usually mean a router ignores probes. Stop shows the partial route. |
| **TCP Port Test** | Enter a host and ports like `443`, `80, 443` or `8000-8005` (max 20). Only test systems you own or may test. A timeout does not prove a port is closed. |
| **Internet Check** | Tests several HTTPS endpoints. One failing endpoint never means "internet down". |
| **Public IP** | Asks an external service for your public address - only when you press the button. |
| **ARP Table / Routing Table / DNS Cache** | Read-only lists. Type in *Filter results...* to narrow them. |
| **Adapter Information** | Compact table of interfaces with speed and traffic counters. `n/a` = Windows did not provide the value. |

### Reading Quick Diagnosis

Findings use cautious wording on purpose - for example *"Possible DNS issue"*. Typical meanings:

- **Gateway does not answer ping but internet works** - the router filters ICMP; usually harmless.
- **Possible DNS issue** - connecting by IP works, names do not resolve. Try another DNS server.
- **Possible DHCP issue** - only a 169.254.x.x address. Reconnect or restart the router.
- **Possible local network or router problem** - gateway silent *and* nothing external works. Restart router/modem, check cable/Wi-Fi.

## 5. Live Monitor

1. **Add target** (name, host/IP, interval 2-3600 s, timeout 200-10000 ms).
2. Select it and press **Start / Stop selected**, or **Start All**.
3. A target turns **No reply** only after 2 consecutive failures, and one outage creates one event (and one more when it recovers).

**Edit**, **Enable / Disable** and **Remove** (with confirmation) manage targets. Targets are saved; monitoring does **not**
start by itself unless you enable it in Settings, and it stops when NetVanta closes. Up to 50 targets.

## 6. History & Reports

Everything you run (except read-only table viewers) and every monitor state change is stored locally. Filter by time range,
tool or text; click a column header to sort; select a row to see its details. **Export selected / all shown** writes CSV or
JSON. **Delete selected** and **Clear all history** ask for confirmation.

## 7. Settings / About

Theme, default ping/monitor values, DNS server and test host, internet endpoints, public-IP endpoint, log level, export folder,
auto-start for the monitor, *Open data folder*, *Open log file*, and *Reset to defaults*. Press **Save settings** to apply.

## 8. Privacy

Settings, history and logs stay on your PC in `%APPDATA%\NetVanta`. No telemetry, no account. NetVanta contacts the internet
only for Internet Check, Public IP, the external steps of Quick Diagnosis, and Dashboard's *Check internet now*.

## 9. Troubleshooting NetVanta itself

| Symptom | What to do |
|---|---|
| "Windows did not return adapter information" | Windows PowerShell must be available and not blocked by policy. |
| Ping shows no reply for a device that is on | Its firewall may block ICMP - try the TCP Port Test. |
| DNS Cache / Routes empty | The *DNS Client* service or PowerShell networking cmdlets may be disabled. |
| Something looks wrong | *Settings > Open log file*, set log level to DEBUG, repeat the action. |
| Windows SmartScreen warns on first run | The installer is not code-signed; choose *More info > Run anyway*. |
