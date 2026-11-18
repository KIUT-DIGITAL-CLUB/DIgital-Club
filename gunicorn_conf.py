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


def container_cpus() -> float:
    """CPUs available to THIS container, not to the host machine.

    multiprocessing.cpu_count() reports the host's cores, so on a shared host
    (Railway, Fly, Kubernetes, ...) it can report 26 cores for a container with
    a 1-CPU quota. Using it to size the worker pool spawns ~53 workers, each
    loading Flask + Pillow + reportlab + cairosvg, and the container is
    OOM-killed in a boot loop. Read the cgroup CPU quota instead.
    """
    # cgroup v2
    try:
        with open("/sys/fs/cgroup/cpu.max", "r") as fh:
            quota_raw, period_raw = fh.read().split()
        if quota_raw != "max":
            quota, period = int(quota_raw), int(period_raw)
            if quota > 0 and period > 0:
                return quota / period
    except Exception:
        pass

    # cgroup v1
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r") as fh:
            quota = int(fh.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r") as fh:
            period = int(fh.read().strip())
        if quota > 0 and period > 0:
            return quota / period
    except Exception:
        pass

    # Not containerised (or no quota set): fall back to the host's cores.
    try:
        return float(len(os.sched_getaffinity(0)))
    except AttributeError:
        return float(multiprocessing.cpu_count() or 1)


def default_workers() -> int:
    cpus = container_cpus()
    calculated = int(2 * cpus + 1)
    # Hard ceiling: this app's workers are memory-hungry (Pillow, reportlab,
    # cairosvg), so never size the pool past what a small container can hold.
    # Raise GUNICORN_WORKERS deliberately once you know the memory limit.
    return max(2, min(calculated, env_int("GUNICORN_MAX_WORKERS", 8)))


workers = env_int("GUNICORN_WORKERS", default_workers())

# Recycle workers periodically so leaked memory (image/PDF generation) is
# reclaimed instead of accumulating until the container is OOM-killed.
max_requests = env_int("GUNICORN_MAX_REQUESTS", 500)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 50)

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


