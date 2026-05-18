"""
Manual crawler script - Run all news crawlers
"""
import os
import re
import sys
import time
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRAPERS_DIR    = Path(__file__).parent / "scrapers"
LOG_DIR         = Path(__file__).parent / "logs" / "crawlers"
SPIDERS         = ['bbc', 'cnn', 'guardian', 'chinadaily']
SPIDER_TIMEOUT  = int(os.getenv('CRAWLER_TIMEOUT', '1800'))  # 30 min default

W = 68  # box width


# ── helpers ──────────────────────────────────────────────────────────────────

def box_top():    print("┌" + "─" * (W - 2) + "┐", flush=True)
def box_sep():    print("├" + "─" * (W - 2) + "┤", flush=True)
def box_bot():    print("└" + "─" * (W - 2) + "┘", flush=True)
def box_row(s):   print(f"│ {s:<{W-3}}│", flush=True)
def box_blank():  box_row("")


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def fmt_duration(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def parse_scrapy_stats(log_path: Path) -> dict:
    stats = {}
    in_block = False
    try:
        with open(log_path, errors='replace') as f:
            for line in f:
                if 'Dumping Scrapy stats' in line:
                    in_block = True
                    continue
                if in_block:
                    m = re.search(r"'([\w/]+)':\s*(\d+)", line)
                    if m:
                        stats[m.group(1)] = int(m.group(2))
                    if line.strip() == '}':
                        break
    except FileNotFoundError:
        pass
    return stats


def last_error_line(log_path: Path) -> str:
    try:
        lines = [l.strip() for l in open(log_path, errors='replace') if 'ERROR' in l and l.strip()]
        return lines[-1][:W - 6] if lines else "see log"
    except FileNotFoundError:
        return "log not found"


# ── spider runner ─────────────────────────────────────────────────────────────

def run_spider(spider_name: str):
    log_path = LOG_DIR / f"{spider_name}.log"
    box_row(f"[{ts()}]  ▶  {spider_name}  starting …")

    start = time.time()
    with open(log_path, 'w') as lf:
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'scrapy', 'crawl', spider_name],
                cwd=str(SCRAPERS_DIR),
                stdout=lf, stderr=lf,
                timeout=SPIDER_TIMEOUT,
            )
            elapsed = time.time() - start
            stats   = parse_scrapy_stats(log_path)
            scraped   = stats.get('item_scraped_count', 0)
            requests  = stats.get('downloader/request_count', 0)
            responses = stats.get('downloader/response_count', 0)
            errs      = stats.get('downloader/exception_count', 0)
            dups      = stats.get('dupefilter/filtered', 0)

            if result.returncode == 0:
                box_row(f"[{ts()}]  ✓  {spider_name}  done in {fmt_duration(elapsed)}")
                box_row(f"          scraped={scraped}  req={requests}  resp={responses}  err={errs}  dup={dups}")
                return spider_name, True, elapsed, stats
            else:
                tip = last_error_line(log_path)
                box_row(f"[{ts()}]  ✗  {spider_name}  FAILED in {fmt_duration(elapsed)}")
                box_row(f"          {tip}")
                return spider_name, False, elapsed, stats

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            stats   = parse_scrapy_stats(log_path)
            scraped = stats.get('item_scraped_count', 0)
            box_row(f"[{ts()}]  ⚠  {spider_name}  TIMEOUT after {fmt_duration(elapsed)}  scraped={scraped}")
            return spider_name, True, elapsed, stats   # partial success

        except Exception as exc:
            elapsed = time.time() - start
            box_row(f"[{ts()}]  ✗  {spider_name}  ERROR: {exc}")
            return spider_name, False, elapsed, {}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    max_workers = int(os.getenv('CRAWLER_MAX_WORKERS', '4'))
    run_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    box_top()
    box_row("AI News Crawler")
    box_sep()
    box_row(f"Started   : {run_ts}")
    box_row(f"Spiders   : {', '.join(SPIDERS)}")
    box_row(f"Workers   : {max_workers} (parallel)")
    box_row(f"Timeout   : {SPIDER_TIMEOUT}s per spider")
    box_row(f"Logs      : {LOG_DIR}")
    box_sep()
    box_row("Live progress:")
    box_blank()

    if not SCRAPERS_DIR.exists():
        box_row(f"ERROR: scrapers dir not found: {SCRAPERS_DIR}")
        box_bot()
        return

    wall_start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(run_spider, s) for s in SPIDERS]
        for f in as_completed(futures):
            results.append(f.result())

    wall_elapsed = time.time() - wall_start

    # ── summary table ────────────────────────────────────────────────────────
    box_blank()
    box_sep()
    box_row("Summary")
    box_sep()
    box_row(f"  {'Spider':<12} {'Status':<10} {'Time':<8} {'Scraped':>7} {'Req':>5} {'Resp':>5} {'Err':>4} {'Dup':>4}")
    box_row("  " + "─" * (W - 4))

    total_scraped = 0
    n_ok = 0
    for spider_name, ok, elapsed, stats in sorted(results, key=lambda r: r[0]):
        scraped   = stats.get('item_scraped_count', 0)
        requests  = stats.get('downloader/request_count', 0)
        responses = stats.get('downloader/response_count', 0)
        errs      = stats.get('downloader/exception_count', 0)
        dups      = stats.get('dupefilter/filtered', 0)
        total_scraped += scraped
        if ok:
            n_ok += 1
            status = "✓ ok"
        else:
            status = "✗ fail"
        box_row(
            f"  {spider_name:<12} {status:<10} {fmt_duration(elapsed):<8} "
            f"{scraped:>7} {requests:>5} {responses:>5} {errs:>4} {dups:>4}"
        )

    box_sep()
    box_row(
        f"  Total: {len(results)} spiders  |  "
        f"Success: {n_ok}  Failed: {len(results)-n_ok}  |  "
        f"Items: {total_scraped}  |  Wall: {fmt_duration(wall_elapsed)}"
    )
    box_row(f"  Logs → {LOG_DIR}/")
    box_bot()


if __name__ == "__main__":
    main()
