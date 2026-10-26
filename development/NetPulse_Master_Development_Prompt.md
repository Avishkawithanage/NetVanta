# NetPulse --- Master Development Prompt

**Project type:** Python desktop application\
**Primary platform:** Windows 10/11\
**Purpose:** A modern, friendly, reliable network troubleshooting and
monitoring toolkit\
**Document role:** Authoritative build specification for an AI coding
assistant or software engineer

------------------------------------------------------------------------

## 1. Role and mission

Act as a senior systems-tool engineer, Python desktop application
architect, network engineer, QA engineer, and UX designer. Build
**NetPulse**, a practical desktop tool that helps users troubleshoot
networks without having to open Command Prompt and manually remember
commands for every routine task.

The application must support **both manual troubleshooting and
guided/automatic diagnosis**:

1.  **Manual mode:** The user selects a tool, enters a target or
    options, presses a button, and sees the result inside NetPulse.
2.  **Guided diagnosis mode:** The user starts a diagnostic sequence.
    NetPulse runs appropriate checks, explains each result in plain
    language, identifies likely causes from evidence, and suggests next
    steps. It must not pretend a diagnosis is certain when evidence is
    inconclusive.

Do not build a large AI system. Core functionality must work locally
without an AI API, account, or internet connection, except for tests
that explicitly need external targets. Diagnosis and recommendations
should be based on deterministic rules and real test results. An
optional future AI integration must not be required for the core
application.

Deliver a working, maintainable application, not merely a mockup, static
dashboard, design prototype, or collection of buttons that do nothing.

## 2. Product principles

-   **Modern but simple:** polished, contemporary interface with a
    restrained colour palette, clear hierarchy, consistent spacing,
    readable typography, attractive status badges, and intuitive icons.
-   **Friendly dashboard:** avoid clutter, excessive cards, nested
    menus, and complicated workflows. Put common actions first and
    advanced details behind expandable sections.
-   **Accurate over impressive:** never fabricate IP addresses, test
    results, latency, packet loss, uptime, or diagnoses.
-   **Real functionality:** every visible control must work or be
    clearly marked as unavailable with a reason. No dead buttons, fake
    progress, placeholder charts, or hard-coded success states.
-   **Responsive interaction:** long-running checks must not freeze the
    UI. Provide progress, cancellation where practical, timeouts, and
    understandable errors.
-   **Safe by default:** diagnostic checks should be read-only. Do not
    automatically change network settings, flush DNS, renew addresses,
    disable adapters, alter routes, or modify firewall rules.
-   **Evidence-based explanations:** distinguish `PASS`, `FAIL`,
    `WARNING`, `SKIPPED`, and `UNKNOWN`. A failed ping alone must not be
    treated as proof that a device is offline.
-   **Windows-first:** implement and test Windows 10/11 behaviour first.
    Clearly detect unsupported platforms and avoid silently running
    incompatible commands.
-   **No duplicated features:** each capability must have one canonical
    implementation and one clear place in the interface. Reuse shared
    services rather than copy-pasting logic.
-   **Privacy:** store data locally by default. Do not upload hostnames,
    IP addresses, logs, or reports to external services without explicit
    user action.
-   **Accessibility:** keyboard navigation, visible focus, adequate
    contrast, clear labels, and useful error messages.
-   **Maintainability:** modular architecture, type hints where useful,
    meaningful names, logging, tests, and documentation.

## 3. Technology stack

Prefer a lightweight, well-supported Python stack:

-   **Python:** Python 3.11 or newer, within dependency compatibility.
-   **GUI:** CustomTkinter for a modern desktop interface; use standard
    Tkinter capabilities where helpful.
-   **Networking:** Python `socket`, `subprocess`, `ipaddress`, and
    `concurrent.futures`.
-   **DNS:** `dnspython` for DNS record queries.
-   **System information:** carefully selected Windows commands and/or
    Windows system APIs. Use a single well-tested adapter-information
    service.
-   **Persistence:** SQLite through Python's standard `sqlite3`.
-   **Charts:** Matplotlib only where a chart adds real value.
-   **Reports:** standard CSV and JSON support; optionally create HTML
    reports using local templates.
-   **Testing:** `unittest` or `pytest` (choose one and use it
    consistently).
-   **Packaging:** PyInstaller for a Windows executable after the app
    works from source.
-   **Code quality:** standard logging, clear exceptions, type hints,
    and optional Ruff for linting.

Keep dependencies minimal. Pin or constrain dependencies in
`requirements.txt`. Do not add a large framework without a clear need.
Never use `shell=True` with untrusted user input. Use argument lists,
validation, timeouts, and safe subprocess handling.

## 4. Main application navigation

Use a simple sidebar or top navigation with these primary sections:

1.  **Dashboard**
2.  **Troubleshooting**
3.  **Live Monitor**
4.  **History & Reports**
5.  **Settings / About**

The main workspace should be clean and consistent. Keep the common
actions visible without forcing users through multiple screens. Use
expandable advanced options for infrequently used settings.

### Visual direction

Use a modern dark theme as the initial default, with an optional light
theme if feasible. Use a restrained palette such as deep navy/charcoal
surfaces, one blue or teal accent, and semantic green/amber/red status
colours. Do not use colour alone to communicate state; include text
labels and icons. Avoid excessive gradients, glowing effects, giant
cards, dense tables, and decorative animation.

Suggested visual components: - compact sidebar with icon and text
labels; - clear page title and short helper description; - status chips
for Online, No reply, Warning, and Error; - consistent
primary/secondary/destructive buttons; - tables with readable row
spacing and sorting where useful; - accessible empty states and loading
states; - copy, export, refresh, and stop actions where relevant.

Do not sacrifice usability or testability for visual effects.

## 5. Feature specification

### 5.1 Dashboard

Provide a quick overview without overwhelming the user:

-   current network adapter / connection summary;
-   local IPv4 address, subnet mask/prefix, default gateway, and DNS
    servers when available;
-   internet connectivity check status, clearly separated from gateway
    reachability;
-   number of configured monitored targets;
-   current monitored-target status;
-   recent connectivity events;
-   quick actions for **IP Configuration**, **Ping**, and **Run Quick
    Diagnosis**.

All dashboard values must come from real system information or recorded
tests. If information is unavailable, show `Unknown` or a clear
explanation, not a fabricated value.

### 5.2 Troubleshooting workspace

This is the core of NetPulse. Provide a clearly labelled
**Troubleshooting** tab containing separate tools or panels. Show
command output and structured summaries inside the app; do not open a
visible CMD window for normal operations.

#### A. IP Configuration

-   `Check IP Configuration` action.
-   List available network adapters.
-   Show adapter name, status, IPv4/IPv6 addresses, subnet/prefix, MAC
    address where available, default gateway, and DNS servers.
-   Provide a detailed view for multiple adapters, including
    disconnected and virtual adapters when the operating system exposes
    them.
-   Distinguish Wi-Fi, Ethernet, VPN, virtual, and other adapter types
    when reliably available.
-   Provide Refresh, Copy Results, and Export options.
-   Do not assume that the first adapter is the active internet adapter.
-   Do not confuse a loopback, link-local, VPN, or virtual-adapter
    address with the primary LAN address.
-   If an elevated command is required, explain why and provide a safe
    fallback when possible; do not silently request administrator
    privileges.

#### B. Ping test

-   Accept a validated hostname or IP address.
-   Configurable packet count, timeout, and interval, with safe sensible
    defaults.
-   Start, Stop, and Clear Results controls.
-   Display each reply or timeout in real time.
-   Summarise sent, received, lost, loss percentage, and min/average/max
    latency when valid samples exist.
-   Show errors such as invalid target, DNS resolution failure,
    permission issue, timeout, and unsupported operation distinctly.
-   Keep command execution out of the GUI thread.
-   Parse Windows output robustly and test it; where practical, use a
    platform-specific adapter behind a common interface.
-   Never display made-up sample replies as live results.
-   Explain that ICMP can be blocked or deprioritised, so no reply does
    not conclusively prove a host is down.

#### C. Continuous Ping / target monitoring

-   Accept one or more user-configured targets.
-   User-configurable check interval and timeout within safe bounds.
-   Live status, latest latency, recent latency history, and recent
    failure count.
-   Start, Stop, Pause/Resume where practical, and remove-target
    actions.
-   Detect state transitions such as reachable → no reply and no reply →
    reachable.
-   Avoid creating duplicate events every interval for one continuous
    outage. Record transitions and optionally periodic summaries.
-   Clearly distinguish "no ping reply" from a confirmed service outage.
-   Keep the application responsive with background workers and clean
    shutdown handling.

#### D. Quick Network Diagnosis

Offer a **Run Quick Diagnosis** workflow that runs independent checks
and shows progress and results. Include, where applicable:

1.  network adapter status;
2.  local IP configuration;
3.  presence of a plausible default gateway;
4.  gateway reachability;
5.  DNS resolution using a configurable test hostname;
6.  external HTTPS connectivity check;
7.  optional user-selected target reachability.

For each step, show status, evidence, short explanation, and a next-step
recommendation. Use deterministic diagnostic rules and confidence
wording such as "Possible DNS issue" rather than claiming certainty. A
failed gateway ping is not definitive if ICMP is filtered. External
checks must have timeouts and must be clearly identified as external.
Let the user see which tests were skipped and why. Provide a copyable or
exportable diagnostic summary.

#### E. DNS Lookup

-   Accept a hostname/domain and query type: A, AAAA, MX, NS, TXT, and
    CNAME where appropriate.
-   Display returned records, resolver used, duration, and
    understandable errors.
-   Permit a configurable DNS resolver, with sensible system-default
    behaviour.
-   Handle no-record responses, NXDOMAIN, timeouts, and resolver
    failures separately.
-   Do not claim that a domain has no DNS records merely because one
    resolver timed out.
-   Provide Copy and Export Results.

#### F. Traceroute

-   Accept a hostname or IP address.
-   Run the platform-appropriate trace command with a bounded timeout
    and hop limit.
-   Display hop number, address/hostname when resolved, and timing
    results where available.
-   Stop or cancel where supported.
-   Explain that `*` or a missing hop can indicate filtering, rate
    limiting, or no response, not necessarily a broken route.
-   Show partial results if the trace times out.
-   Do not block the GUI.

#### G. ARP table viewer

-   Read and display available ARP/neighbour entries.
-   Show IP address, MAC address, and interface where the platform
    provides them.
-   Refresh and copy/export results.
-   Explain that ARP/neighbour tables may be incomplete or stale and do
    not list every device on the network.

#### H. Routing table viewer

-   Read and display routes using a platform-appropriate method.
-   Show destination/network, netmask or prefix, gateway/next hop,
    interface, and metric where available.
-   Format routes in a readable table.
-   Provide refresh, copy, and export.
-   This is a read-only viewer in the initial release; do not add,
    delete, or change routes.

#### I. DNS cache viewer

-   On supported Windows versions, retrieve the local DNS resolver cache
    using a suitable read-only method.
-   Provide refresh, search/filter, and copy/export.
-   If the output is too large, paginate or filter it.
-   Do not flush or alter the DNS cache in the initial release.
-   If a method is unsupported or restricted, show an actionable
    explanation rather than crashing.

#### J. TCP port connectivity test

-   Accept a hostname/IP and one TCP port, with optional bounded testing
    of a user-specified list of ports.
-   Validate port values from 1 to 65535.
-   Use short configurable connection timeouts.
-   Display connected, refused, timed out, DNS error, or other error as
    distinct outcomes where determinable.
-   Show connection time when measurable.
-   Explain that a timeout does not prove a port is closed; filtering
    and routing issues can cause it.
-   Limit concurrency and validate inputs.
-   Intended for systems and services the user owns or is authorised to
    test. Do not add stealth scanning, exploitation, or evasion
    features.

#### K. Adapter information

-   Show interface names, operational status, addresses, and available
    interface statistics.
-   Provide a refresh action.
-   Reuse the same underlying adapter-information service as IP
    Configuration instead of implementing the same parsing logic twice.
-   Clearly identify fields that the operating system does not provide.

#### L. Public IP check

-   Optional action to query an external public-IP endpoint.
-   State clearly that this contacts an external service.
-   Use a short timeout and handle unavailable service, proxy, VPN, and
    multiple-egress ambiguity.
-   Do not run automatically on every app launch.
-   Do not store or transmit the result beyond local history unless the
    user explicitly exports it.

#### M. Internet connectivity check

-   Test configured external HTTPS endpoint(s) with a timeout.
-   Keep internet connectivity separate from ICMP reachability.
-   Report DNS, connection, TLS, HTTP, and timeout errors as accurately
    as possible.
-   Do not label the whole internet "down" based on one endpoint alone.
    Permit more than one endpoint or a user-selected endpoint.

#### N. Copy and export

For applicable tools: - Copy concise summary to clipboard. - Export
raw/structured results to CSV or JSON. - Include timestamp, tool,
target, status, and relevant measurements. - Clearly distinguish raw
output from NetPulse's interpretation. - Handle clipboard and file
permission failures gracefully.

### 5.3 Live Monitor

-   Add, edit, enable, disable, and remove monitoring targets.
-   Support IP addresses and hostnames.
-   Configure check interval and timeout with validated limits.
-   Show target, type, current state, last checked time, latest latency,
    and recent failure information.
-   Provide Start All, Stop All, and per-target controls.
-   Record meaningful state transitions and avoid duplicate outage spam.
-   Save target configuration locally and restore it on next launch.
-   Let users choose whether monitoring starts automatically; default to
    not starting hidden background checks without user consent.
-   Avoid unbounded threads, excessive requests, and high CPU use.

### 5.4 History & Reports

-   Store relevant test history and state transitions in SQLite.
-   Provide time filters, tool/target filters, search, and sorting.
-   Show timestamps in local time and store a consistent canonical
    timestamp internally.
-   Export selected rows or reports to CSV/JSON.
-   Provide a clear option to delete selected history and a confirmation
    for destructive local-data actions.
-   Keep report output truthful and reproducible.
-   Avoid storing unnecessary sensitive information.

### 5.5 Settings / About

-   Theme preference if both themes are supported.
-   Default ping count, timeout, monitoring interval, and DNS resolver.
-   Optional startup behaviour.
-   Log level and local log location.
-   Data export location preference where practical.
-   App version, Python version, dependency information, and
    troubleshooting guidance.
-   A privacy note explaining what data remains local and when external
    endpoints are contacted.
-   A reset-to-defaults option with confirmation.

## 6. User experience and interaction rules

-   Keep the primary workflow obvious: choose a tool → enter
    target/options → press Run → view results → copy/export if needed.
-   Use consistent labels and button placement across all tools.
-   Disable only controls that genuinely cannot be used in the current
    state.
-   Validate input before starting a process and explain how to correct
    invalid input.
-   Use visible loading/progress indicators without blocking
    interaction.
-   Allow cancellation for long-running tasks where technically
    possible.
-   Do not clear useful prior results without user intent.
-   Keep raw output available in an expandable details panel when a
    command-based check is used.
-   Display a concise summary first; keep technical details available
    for engineers.
-   Never show a success state before the operation completes
    successfully.
-   Do not label an operation "complete" if it was cancelled or only
    partially completed.
-   Ensure keyboard focus, tab navigation, and window resizing work.
-   Confirm before deleting targets or history.
-   Do not display stack traces to ordinary users. Record diagnostic
    details in a local log and show a clear error message.

## 7. Architecture and code organisation

Use a modular structure similar to the following. Adjust only when there
is a clear engineering reason and document the decision.

``` text
NetPulse/
├── app.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── config/
│   └── defaults.py
├── netpulse/
│   ├── __init__.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard_view.py
│   │   ├── troubleshooting_view.py
│   │   ├── monitor_view.py
│   │   ├── history_view.py
│   │   ├── settings_view.py
│   │   └── widgets/
│   ├── services/
│   │   ├── ip_config.py
│   │   ├── ping_service.py
│   │   ├── diagnosis_service.py
│   │   ├── dns_service.py
│   │   ├── traceroute_service.py
│   │   ├── arp_service.py
│   │   ├── route_service.py
│   │   ├── dns_cache_service.py
│   │   ├── tcp_check_service.py
│   │   ├── adapter_service.py
│   │   └── internet_check_service.py
│   ├── data/
│   │   ├── database.py
│   │   ├── repositories.py
│   │   └── settings_store.py
│   ├── models/
│   │   └── results.py
│   └── utils/
│       ├── validation.py
│       ├── subprocess_runner.py
│       ├── logging_setup.py
│       └── export.py
├── tests/
│   ├── test_validation.py
│   ├── test_ping_service.py
│   ├── test_dns_service.py
│   ├── test_diagnosis_service.py
│   ├── test_database.py
│   └── test_exports.py
└── screenshots/
```

Keep UI code separate from networking logic. UI event handlers should
call service methods and receive structured results. Do not parse
command output inside UI widgets. Use typed result models or consistent
data structures with fields for status, summary, details, timestamp,
target, duration, and errors where relevant.

## 8. Reliability and error handling requirements

-   Every subprocess and network operation must have a timeout or a
    clearly justified bounded lifetime.
-   Use safe argument arrays and avoid passing raw user input through a
    shell.
-   Validate hostnames, IP addresses, ports, counts, intervals, and file
    paths.
-   Treat empty results, malformed output, DNS failures, permission
    failures, unsupported commands, and cancelled operations as normal
    error cases.
-   Do not assume command output language is always English if a more
    robust system interface is available.
-   Do not make parsing depend on one exact whitespace layout.
-   Ensure background workers report results back to the GUI thread
    safely.
-   On shutdown, stop scheduled checks and clean up workers without
    hanging indefinitely.
-   Use database transactions and parameterised SQL.
-   Avoid duplicate database rows caused by repeated UI clicks or event
    retries.
-   Keep logs useful but do not write credentials or unnecessary
    sensitive information.
-   Fail gracefully when a dependency or external endpoint is
    unavailable.
-   Do not suppress exceptions silently.
-   Do not silently substitute dummy data when a real operation fails.
-   Handle Windows paths, Unicode hostnames where supported, and
    filenames with spaces.
-   Do not require administrator access for ordinary read-only features
    unless the specific operation truly requires it.

## 9. Security and privacy

-   This is a defensive, administrative diagnostics tool.
-   Do not add exploit code, credential collection, stealth scanning,
    persistence, or evasion.
-   Port checks must be bounded and intended for authorised targets.
-   External requests must be explicit, documented, and time-limited.
-   Keep all history and settings local by default.
-   Do not embed API keys, credentials, or secrets in source code.
-   Do not execute shell commands assembled from untrusted strings.
-   Do not change the user's system configuration in the initial
    release.
-   Do not collect telemetry by default.

## 10. Testing and quality assurance

Do not claim the app is fully working until relevant checks have
actually been run. Use unit tests with mocks for network and subprocess
behaviour so tests do not depend on the public internet.

Test at least:

1.  Valid and invalid IPv4/IPv6 addresses and hostnames.
2.  Invalid ports, packet counts, intervals, and timeouts.
3.  Ping success, no reply, DNS failure, command failure, and timeout.
4.  Zero replies and packet-loss calculations without divide-by-zero
    errors.
5.  Min/average/max latency with empty and non-empty samples.
6.  DNS success, no records, NXDOMAIN, timeout, and resolver failure.
7.  Traceroute partial output and timeout.
8.  TCP connected, refused, timed out, and DNS error cases.
9.  Diagnosis logic when gateway, DNS, or HTTPS checks fail
    independently.
10. SQLite create/read/update/delete and database error handling.
11. CSV/JSON export correctness and file-write failures.
12. UI responsiveness while a long test is running.
13. Stop/cancel behaviour and clean application shutdown.
14. Duplicate monitoring-event prevention.
15. Missing commands, missing permissions, unsupported platforms, and
    malformed command output.
16. Repeated clicks and rapid start/stop actions.
17. Application start when no internet connection is available.
18. Data persistence and settings reload.

Use mocks or controlled local test servers where practical. Avoid
relying on a public host being reachable during automated tests. Run the
tests, fix failures, and report which tests were run and their results.
Never invent test results.

## 11. Delivery requirements

Deliver all of the following:

-   Working Python source code.
-   Clear installation and launch instructions.
-   A `requirements.txt` with necessary dependencies.
-   A professional README with purpose, features, screenshots,
    limitations, setup, usage, testing, and troubleshooting.
-   A `.gitignore` that excludes virtual environments, caches, local
    databases, logs, build artifacts, and secrets.
-   Unit tests for core services and important calculations.
-   Useful sample configuration only; never present sample test output
    as live data.
-   A concise architecture explanation.
-   Instructions for building a Windows executable with PyInstaller.
-   A list of known platform limitations and any feature that is
    incomplete.
-   A final verification checklist.

## 12. Implementation workflow

Work in small, verifiable stages. Do not generate a huge untested code
dump.

### Stage 1 --- Foundation

-   Inspect the environment and confirm the supported Python version.
-   Create the project structure and dependency list.
-   Establish the theme, main window, navigation, logging, and result
    models.
-   Add basic tests and verify the app launches.

### Stage 2 --- Core diagnostics

-   Implement input validation and a safe subprocess/network execution
    layer.
-   Implement IP configuration and ping.
-   Add unit tests for successful and failed operations.
-   Verify the GUI remains responsive.

### Stage 3 --- Additional troubleshooting

-   Implement continuous ping, quick diagnosis, DNS lookup, traceroute,
    TCP checks, ARP, routes, DNS cache, adapter details, and external
    connectivity checks.
-   Reuse shared services and result models.
-   Add error cases and tests for each feature.

### Stage 4 --- Monitoring and storage

-   Implement target management, background polling, state-transition
    detection, SQLite persistence, and history.
-   Test cancellation, repeated clicks, duplicate-event handling, and
    clean shutdown.

### Stage 5 --- Reports and polish

-   Implement exports, accessible tables, useful empty/loading/error
    states, theme settings, and documentation.
-   Confirm every visible control has a real behaviour.
-   Remove duplicate code and unused dependencies.

### Stage 6 --- Verification and packaging

-   Run tests and static checks.
-   Launch the application and perform a manual smoke test on Windows.
-   Fix discovered defects before packaging.
-   Build and test the PyInstaller executable if the environment
    supports it.
-   Record any tests or platform checks that could not be run.

If working in an existing repository, inspect its structure and current
behaviour first. Preserve working functionality. Avoid destructive
rewrites, never overwrite user data without permission, and explain
significant changes.

## 13. Definition of done

The project is ready for its first release only when:

-   [ ] The app launches without an unhandled exception.
-   [ ] Navigation and theme are consistent and easy to understand.
-   [ ] IP Configuration shows actual available system data.
-   [ ] Ping accepts a target and displays actual results.
-   [ ] Continuous monitoring can start and stop safely.
-   [ ] Quick Diagnosis runs real checks and provides evidence-based
    explanations.
-   [ ] DNS, traceroute, ARP, routing table, DNS cache, TCP checks,
    adapter information, and connectivity tools either work on the
    supported platform or clearly explain their limitation.
-   [ ] Long-running tasks do not freeze the interface.
-   [ ] Timeouts, errors, and cancellation are handled.
-   [ ] Monitoring targets and history persist correctly.
-   [ ] CSV/JSON exports contain actual selected results.
-   [ ] No visible button is fake or non-functional.
-   [ ] There are no fabricated live results or unsupported certainty
    claims.
-   [ ] Tests have been run and their results are documented.
-   [ ] README, installation instructions, `.gitignore`, and packaging
    instructions are present.
-   [ ] Known limitations are disclosed honestly.

## 14. Final instruction to the coding assistant

Before implementation, summarise the architecture and identify any
genuine blockers. Then build the application incrementally, verifying
each stage. Make sensible engineering decisions without repeatedly
asking about minor details already specified here. Ask the user only
when a decision materially affects functionality, safety, compatibility,
or existing data.

Prioritise correctness, usability, maintainability, and real-world
troubleshooting value. Do not claim "perfect" or "fully tested" unless
evidence supports the claim. If something cannot be implemented or
verified in the current environment, state exactly what remains and
provide a practical next step.

**Product outcome:** NetPulse should feel like a clean, modern,
beginner-friendly desktop toolkit that helps a network engineer inspect
IP settings, test connectivity, investigate common network problems
manually, and run a guided diagnosis---all from one application without
needing to open CMD for routine checks.
