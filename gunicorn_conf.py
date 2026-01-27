#Note: Do not touch if you don't understand anything
import multiprocessing
import os


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None and value.strip() != "" else default


bind = f"0.0.0.0:{env_int('PORT', 5051)}"

# Calculate workers: 2-4 x CPU cores is common. We'll use 2 * cores + 1
cores = multiprocessing.cpu_count() or 1
workers = env_int("GUNICORN_WORKERS", 2 * cores + 1)

# Async workers can help with I/O heavy Flask apps; default to sync for simplicity
worker_class = env_str("GUNICORN_WORKER_CLASS", "sync")

# Keep connections alive for reverse proxies
keepalive = env_int("GUNICORN_KEEPALIVE", 5)

# Graceful timeouts
timeout = env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Log to stdout/stderr for container visibility
accesslog = "-"
errorlog = "-"
loglevel = env_str("GUNICORN_LOGLEVEL", "info")

# Limit request size (in bytes) to prevent abuse; Flask also enforces MAX_CONTENT_LENGTH
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190


