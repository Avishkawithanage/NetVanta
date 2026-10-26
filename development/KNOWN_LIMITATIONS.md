# Known limitations

- **Windows 10/11 only.** `app.py` exits with a message on other platforms.
- **Unsigned installer.** Windows SmartScreen may show a warning on first run (choose *More info > Run anyway*). Code-signing
  needs a paid certificate.
- **ICMP depends on the network.** Firewalls and routers may drop ping or traceroute probes; NetVanta explains this but cannot bypass it.
- **No real cable test.** A laptop cannot measure cable length, detect a short/open circuit (that needs TDR hardware) or read the
  switch port (LLDP/CDP needs a packet-capture driver). *Cable & Link Health* only infers trouble from speed/duplex, error counters,
  link-drop events and burst-ping loss. The link-drop reading depends on the NIC driver writing events and is best effort.
- **Not every NIC reports the same data.** Maximum supported speed, duplex and counters vary by driver; missing values show as `n/a`.
- **Full Analysis on Wi-Fi.** If no wired link is in use the cable layer is shown as SKIPPED.
- **IPv6.** Adapters, DNS (AAAA) and ping/TCP to IPv6 literals work, but diagnosis steps focus on IPv4 gateways.
- **Windows PowerShell required** for adapter, routing-table and DNS-cache data (present on every Windows 10/11 install unless removed by policy).
- **Loopback refusal timing.** Windows can take about 2 s to report "connection refused" on a closed local port; use a timeout of 3 s or more.
- **Traceroute/ping output** is parsed from the built-in tools. Unusual localised output may be shown raw rather than parsed.
- **Live Monitor** runs only while NetVanta is open (no background service) and uses ICMP only.
- **Not implemented by design (v1.0):** changing system settings (DNS flush, route edits, adapter reset), port scanning of large ranges,
  AI features, telemetry.
- **GUI automation tests** are not included; the UI was verified by launching it (`--smoke-test`, screenshots) and by manual use.
