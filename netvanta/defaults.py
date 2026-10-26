"""Default settings and validation limits."""

DEFAULT_SETTINGS: dict = {
    "theme": "dark",
    "ping_count": 4,
    "ping_timeout_ms": 2000,
    "ping_interval_s": 1.0,
    "monitor_interval_s": 5,
    "monitor_timeout_ms": 2000,
    "monitor_autostart": False,
    "dns_resolver": "",
    "dns_test_host": "www.microsoft.com",
    "internet_endpoints": [
        "https://www.msftconnecttest.com/connecttest.txt",
        "https://www.cloudflare.com/cdn-cgi/trace",
        "https://www.google.com/generate_204",
    ],
    "public_ip_endpoint": "https://api.ipify.org",
    "log_level": "INFO",
    "export_dir": "",
}

# (minimum, maximum) for numeric settings
LIMITS: dict[str, tuple[float, float]] = {
    "ping_count": (1, 100),
    "ping_timeout_ms": (200, 10000),
    "ping_interval_s": (0.2, 60),
    "monitor_interval_s": (2, 3600),
    "monitor_timeout_ms": (200, 10000),
}

THEMES = ("dark", "light", "system")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
MAX_PORTS_PER_TEST = 20
MAX_TRACE_HOPS = 30
MAX_MONITOR_TARGETS = 50
