#!/usr/bin/env python3
"""Watchdog for BaoStock importer — ensures importer keeps running.

Architecture-level fix: instead of complex fault tolerance in the importer itself,
use a simple watchdog process that monitors and restarts the importer.

Benefits:
  - Importer stays simple (single process, single thread)
  - Watchdog handles crashes, OOM, freezes
  - No complex state management
  - Easy to understand and debug
"""

import subprocess
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("watchdog.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

IMPORTER_CMD = [
    sys.executable, "-u", "-m",
    "tradingagents.dataflows.a_stock.baostock_importer",
    "--intervals", "30,15,5"
]

LOG_FILE = "baostock_import.log"
MAX_RESTARTS_PER_HOUR = 6  # Prevent restart loops
RESTART_COOLDOWN = 300  # 5 minutes between restarts


def is_importer_healthy(log_file: Path, max_age_seconds: int = 600) -> bool:
    """Check if importer is making progress (log updated recently)."""
    if not log_file.exists():
        return False
    mtime = log_file.stat().st_mtime
    age = time.time() - mtime
    return age < max_age_seconds


def run_importer():
    """Run importer as subprocess, return exit code."""
    logger.info("Starting importer: %s", " ".join(IMPORTER_CMD))
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as logf:
            result = subprocess.run(
                IMPORTER_CMD,
                stdout=logf,
                stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent.parent.parent.parent,
            )
        return result.returncode
    except Exception as exc:
        logger.error("Failed to start importer: %r", exc)
        return 1


def main():
    restart_count = 0
    last_restart_time = 0
    
    logger.info("Watchdog started, monitoring importer")
    
    while True:
        # Check if we should restart
        log_file = Path(__file__).parent.parent.parent.parent / LOG_FILE
        healthy = is_importer_healthy(log_file)
        
        if healthy:
            # Importer is running fine, wait and check again
            time.sleep(60)
            continue
        
        # Importer is not healthy, check if we can restart
        now = time.time()
        if now - last_restart_time < RESTART_COOLDOWN:
            logger.warning("Importer down but cooldown active, waiting...")
            time.sleep(60)
            continue
        
        if restart_count >= MAX_RESTARTS_PER_HOUR:
            logger.error("Too many restarts (%d/hour), backing off for 1 hour", restart_count)
            time.sleep(3600)
            restart_count = 0
            continue
        
        # Restart importer
        logger.info("Importer not healthy, restarting (restart #%d this hour)", restart_count + 1)
        exit_code = run_importer()
        
        restart_count += 1
        last_restart_time = time.time()
        
        if exit_code == 0:
            logger.info("Importer exited cleanly (all tasks complete)")
            break
        
        logger.warning("Importer exited with code %d", exit_code)


if __name__ == "__main__":
    main()
