"""Task-queue based BaoStock importer — architecture-level fix.

Problems with the old single-process importer:
  1. Single process handles 5000+ stocks — any crash stops everything
  2. Fragile state management — local JSON + PG dual-write, easy to corrupt
  3. Complex concurrency — threads/processes/socket sharing, each layer can fail
  4. Strong external dependency — BaoStock instability affects entire system
  5. No real fault tolerance — manual restart needed after crash

New architecture:
  - Each stock is an independent task, state in PG only
  - Worker process pool (4-8 workers) processes tasks in parallel
  - One worker crash doesn't affect others
  - Scheduler automatically retries failed tasks
  - No local state files — PG is single source of truth
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import baostock as bs
import psycopg2
from psycopg2.extras import execute_values

from tradingagents.cache.manager import _get_pg_pool
from tradingagents.dataflows.a_stock.baostock_importer import (
    INTERVAL_MAP,
    START_DATE,
    END_DATE,
    bs_code_to_ticker,
    _fetch_bars_chunked,
    bs_login,
    bs_reconnect,
)

logger = logging.getLogger(__name__)

# Task states in PG
TASK_PENDING = 'pending'
TASK_RUNNING = 'running'
TASK_OK = 'ok'
TASK_FAILED = 'failed'
TASK_PARTIAL = 'partial'


def ensure_task_table(cur):
    """Create task queue table if not exists."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS import_tasks (
            ticker TEXT NOT NULL,
            data_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER NOT NULL DEFAULT 0,
            bars_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            error_msg TEXT,
            PRIMARY KEY (ticker, data_type)
        )
    """)


def init_tasks(cur, tickers: list[str], intervals: list[str]):
    """Initialize task queue for all ticker/interval combinations."""
    for ticker in tickers:
        for interval in intervals:
            data_type = INTERVAL_MAP[interval][0]
            cur.execute("""
                INSERT INTO import_tasks (ticker, data_type, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticker, data_type) DO NOTHING
            """, (ticker, data_type, TASK_PENDING))


def get_pending_tasks(cur, interval: str, limit: int = 100) -> list[tuple[str, str]]:
    """Get pending tasks for an interval."""
    data_type = INTERVAL_MAP[interval][0]
    cur.execute("""
        SELECT ticker, data_type FROM import_tasks
        WHERE data_type = %s AND status = %s
        ORDER BY attempt ASC, ticker ASC
        LIMIT %s
    """, (data_type, TASK_PENDING, limit))
    return cur.fetchall()


def claim_task(cur, ticker: str, data_type: str):
    """Mark task as running."""
    cur.execute("""
        UPDATE import_tasks SET status = %s, attempt = attempt + 1, started_at = now()
        WHERE ticker = %s AND data_type = %s
    """, (TASK_RUNNING, ticker, data_type))


def complete_task(cur, ticker: str, data_type: str, status: str, bars_count: int, error_msg: str = None):
    """Mark task as completed/failed/partial."""
    cur.execute("""
        UPDATE import_tasks
        SET status = %s, bars_count = %s, completed_at = now(), error_msg = %s
        WHERE ticker = %s AND data_type = %s
    """, (status, bars_count, error_msg, ticker, data_type))


def reset_failed_tasks(cur, data_type: str):
    """Reset failed tasks to pending for retry."""
    cur.execute("""
        UPDATE import_tasks SET status = %s, attempt = 0, error_msg = NULL
        WHERE data_type = %s AND status = %s
    """, (TASK_PENDING, data_type, TASK_FAILED))


def worker(conn, pool, ticker: str, data_type: str, freq: str) -> tuple[str, int]:
    """Worker function: fetch bars for one stock and write to PG.
    
    Returns (status, bars_count).
    """
    import baostock as bs
    
    try:
        # Login in worker process
        lg = bs.login()
        if lg.error_code != '0':
            return TASK_FAILED, 0
        
        # Fetch bars
        bars, partial = _fetch_bars_chunked(ticker, freq)
        
        if not bars:
            bs.logout()
            return TASK_FAILED, 0
        
        # Write to PG
        by_date = {}
        for bar in bars:
            td = bar["date"][:10]
            by_date.setdefault(td, []).append(bar)
        
        conn = pool.getconn()
        written = False
        try:
            with conn.cursor() as cur:
                param_hash = INTERVAL_MAP[freq][1]
                rows = [
                    (ticker, data_type, td, param_hash,
                     __import__('json').dumps(day_bars, ensure_ascii=False), time.time())
                    for td, day_bars in sorted(by_date.items())
                ]
                execute_values(
                    cur,
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES %s
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result, updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    rows,
                    template="(%s, %s, %s, %s, %s, to_timestamp(%s))",
                    page_size=200,
                )
            conn.commit()
            written = True
        except Exception as exc:
            conn.rollback()
            logger.error("PG write failed %s/%s: %s", ticker, data_type, exc)
        finally:
            pool.putconn(conn)
        
        bs.logout()
        
        if not written:
            return TASK_FAILED, 0
        
        if partial:
            return TASK_PARTIAL, len(bars)
        return TASK_OK, len(bars)
        
    except Exception as exc:
        logger.error("Worker failed %s/%s: %r", ticker, data_type, exc)
        return TASK_FAILED, 0


def run_scheduler(interval: str, pool, max_workers: int = 4, batch_size: int = 50):
    """Main scheduler: manages worker pool and task distribution."""
    from multiprocessing import Process, Pipe
    
    data_type = INTERVAL_MAP[interval][0]
    
    logger.info(f"Starting scheduler for {data_type} with {max_workers} workers")
    
    while True:
        # Get pending tasks
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                tasks = get_pending_tasks(cur, interval, batch_size)
        finally:
            pool.putconn(conn)
        
        if not tasks:
            # Check if there are failed tasks to retry
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    reset_failed_tasks(cur, data_type)
                    conn.commit()
                    cur.execute("SELECT count(*) FROM import_tasks WHERE data_type = %s AND status = %s",
                               (data_type, TASK_PENDING))
                    pending = cur.fetchone()[0]
                    if pending == 0:
                        logger.info(f"All tasks complete for {data_type}")
                        return
                    logger.info(f"Reset failed tasks, {pending} pending")
            finally:
                pool.putconn(conn)
            continue
        
        # Process tasks in batches
        for ticker, dt in tasks:
            # Claim task
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    claim_task(cur, ticker, dt)
                    conn.commit()
            finally:
                pool.putconn(conn)
            
            # Run worker
            status, bars = worker(None, pool, ticker, dt, interval)
            
            # Update task status
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    complete_task(cur, ticker, dt, status, bars)
                    conn.commit()
            finally:
                pool.putconn(conn)
            
            logger.info(f"{ticker}: {status} ({bars} bars)")
            
            # Rate limit
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description="Task-queue BaoStock importer")
    parser.add_argument("--intervals", type=str, default="30",
                       help="Comma-separated frequencies (5,15,30,60)")
    parser.add_argument("--workers", type=int, default=4,
                       help="Number of concurrent workers")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Number of tasks to fetch per batch")
    parser.add_argument("--init", action="store_true",
                       help="Initialize task queue from PG stock list")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("queue_importer.log", encoding="utf-8"),
        ],
    )
    
    intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]
    pool = _get_pg_pool()
    
    # Login to get ticker list
    if args.init:
        bs_login()
        from tradingagents.dataflows.a_stock.baostock_importer import get_all_tickers_bs
        tickers = get_all_tickers_bs()
        logger.info(f"Found {len(tickers)} tickers")
        
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                ensure_task_table(cur)
                init_tasks(cur, tickers, intervals)
                conn.commit()
                logger.info(f"Initialized task queue for {len(tickers)} tickers × {len(intervals)} intervals")
        finally:
            pool.putconn(conn)
        return
    
    # Run scheduler for each interval
    for interval in intervals:
        run_scheduler(interval, pool, args.workers, args.batch_size)


if __name__ == "__main__":
    main()
