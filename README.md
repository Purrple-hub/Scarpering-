# Advanced Async Web Crawler

A production-grade web crawler built with Python, combining advanced features like adaptive rate limiting, near-duplicate detection, proxy rotation, domain health management, memory optimization, sitemap discovery, and a full PyQt6 GUI.

No headless browser required — it's fast, lightweight, and ready for academic research, SEO analysis, or large-scale data collection.

---

## Features

- **Async crawling** with `curl_cffi` (browser impersonation) and `selectolax` parsing
- **Adaptive rate limiting** via PID-like control based on errors, latency, memory, and queue pressure
- **Smart deduplication**:
  - Scalable Bloom filter for URL tracking
  - SHA-256 exact content dedup with LRU cache
  - Simhash + MinHash LSH for near-duplicate detection
- **Domain health management** with exponential backoff for blocked/failing domains
- **Proxy support** with automatic fetching, validation, rotation, and blacklisting
- **Sitemap discovery** — reads `robots.txt` and `sitemap.xml` (including nested indexes) to seed URLs
- **Embedded JSON link extraction** — pulls URLs from `__NEXT_DATA__`, JSON-LD, iframes, and meta refresh tags
- **Multiple output formats** — JSONL, JSON, CSV, SQLite (WAL mode)
- **ZIP extraction** — recursively processes HTML files inside ZIP archives
- **Dynamic worker scaling** — adjusts concurrency based on queue size and system load
- **Memory optimization** — periodic GC calls and `malloc_trim` (Linux)
- **GUI** — PyQt6 interface with live stats, console, file manager
- **Headless mode** — fully configurable via CLI and JSON config

---

## Installation

### Requirements
- Python 3.10+
- Dependencies are auto-installed on first run (see `crawler/package_manager.py`)

### Manual install

```bash
git clone https://github.com/Purrple-hub/Scarpering-
cd webcrawler
pip install -r requirements.txt

---

## Usage

### Headless mode

```bash
python main.py --headless --url https://example.com --max-pages 500
```

Common CLI options:

| Flag | Description |
|------|-------------|
| `--headless` | Run without GUI |
| `--config <file>` | Path to JSON config file |
| `--url <url>` | Seed URL(s) (can repeat) |
| `--max-pages <n>` | Maximum pages to crawl |
| `--output-dir <dir>` | Output directory |

If `--url` is provided, the crawler runs headless automatically.

### GUI mode

```bash
python main.py
```

The GUI has three tabs:
- **Controls** — start/stop crawl, seed URL input, live stats table, console output
- **Configuration** — edit max depth, max pages, concurrency, timeout, output dir, toggles
- **Files** — browse, preview, compress, and delete output files

---

## Configuration

All settings are stored in `crawler/settings.py` (dataclass). You can override via:

1. **JSON config file** (default `config.json`)
2. **Environment variables** prefixed with `CRAWLER_`
3. **GUI** controls

Example `config.json`:

```json
{
  "seed_urls": ["https://example.com"],
  "max_depth": 3,
  "max_pages": 500,
  "concurrency": 0,
  "timeout": 15.0,
  "retries": 3,
  "backoff_factor": 0.5,
  "base_delay": 0.1,
  "output_dir": "crawled_data",
  "output_formats": ["jsonl", "sqlite"],
  "follow_external": false,
  "max_page_size": 5242880,
  "enable_dedup": true,
  "near_dup_threshold": 0.85,
  "simhash_bits": 64,
  "minhash_perms": 128,
  "minhash_bands": 16,
  "lsh_max_docs": 5000,
  "use_proxy": false,
  "proxy_sources": [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
  ],
  "ssl_verify": false,
  "batch_size": 50,
  "gc_interval": 100,
  "memory_limit_mb": 1024,
  "zip_extract": true,
  "log_file": "crawler.log",
  "use_sitemap": true
}
```

### Environment variables

Any setting can be overridden with `CRAWLER_<SETTING_NAME>` (uppercase). Examples:

```bash
export CRAWLER_MAX_PAGES=1000
export CRAWLER_USE_PROXY=true
export CRAWLER_OUTPUT_DIR=/tmp/crawl
```

---

## Output Data

Output files are saved in the configured output directory (default `crawled_data/`).

- `pages.jsonl` — one JSON object per page (if `jsonl` enabled)
- `pages.json` — full array of pages (if `json` enabled)
- `pages.csv` — tabular CSV (if `csv` enabled)
- `crawled_pages.db` — SQLite database (if `sqlite` enabled)

Each page object contains:

```json
{
  "url": "https://example.com/page",
  "title": "Page Title",
  "content": "Extracted text...",
  "quality_score": 7,
  "depth": 0,
  "domain": "example.com",
  "content_hash": "sha256...",
  "timestamp": "2024-01-01 12:00:00"
}
```

---

## Testing

A full test suite is provided in `tests/`. It covers every major component.

Run all tests:

```bash
python tests/test-main.py
```

This writes a detailed report to `tests/test_results.txt` with pass/fail counts and tracebacks.

Test files:

- `test_settings.py` — config loading, env overrides
- `test_dedup.py` — Bloom filter, Simhash, MinHash, LSH
- `test_domain_health.py` — backoff and cooldown logic
- `test_rate_limiter.py` — adaptive delay calculations
- `test_proxy.py` — proxy fetching, rotation, blacklisting
- `test_quality.py` — content quality scoring
- `test_storage.py` — file management, SQLite, compression
- `test_crawler.py` — URL normalization, HTML parsing, link queueing
- `test_gui.py` — PyQt6 window creation (offscreen)
- `test_discovery.py` — sitemap parsing, embedded JSON extraction

---

## Project Structure

```
webcrawler/
├── main.py
├── requirements.txt
├── config.json
├── crawler/
│   ├── __init__.py
│   ├── settings.py
│   ├── signals.py
│   ├── package_manager.py
│   ├── dedup.py
│   ├── domain_health.py
│   ├── rate_limiter.py
│   ├── proxy.py
│   ├── quality.py
│   ├── storage.py
│   ├── discovery.py
│   └── crawler.py
├── gui/
│   ├── __init__.py
│   ├── worker.py
│   └── main_window.py
└── tests/
    ├── test-main.py
    ├── test_settings.py
    ├── test_dedup.py
    ├── test_domain_health.py
    ├── test_rate_limiter.py
    ├── test_proxy.py
    ├── test_quality.py
    ├── test_storage.py
    ├── test_crawler.py
    ├── test_gui.py
    └── test_discovery.py
```

---

## Performance Notes

- **Concurrency**: Set `concurrency: 0` to auto-scale based on CPU cores.
- **Rate limiting**: The adaptive limiter prevents hammering and adjusts to server/network conditions.
- **Memory**: Bloom filters and LRU caches keep memory bounded. `lsh_max_docs` controls MinHash LSH size.
- **Batching**: Writes are batched (`batch_size`) to reduce I/O overhead.
- **Session reuse**: HTTP sessions are reused per domain to reduce handshake costs.

---

## Troubleshooting

### Crawler returns very few URLs
- Check `crawler.log` for errors or blocked status codes.
- If the site is JavaScript-heavy, static HTML may contain no links. Enable `use_sitemap` (default) to seed from sitemap.xml.
- Verify `follow_external` is `false` if you only want internal pages.
- Try increasing `max_depth` and `max_pages`.

### "Sitemap discovery found 0 additional URLs"
- The site may not have a sitemap or robots.txt. The crawler will still extract links from embedded JSON and standard HTML.
- Some sites block non-browser requests. Consider setting `use_proxy: true`.

### High error rate
- Increase `timeout` and `retries`.
- Enable proxies and configure `proxy_sources`.
- Check if the target site requires specific headers or cookies (not currently supported).

### SQLite database locked
- The database uses WAL mode; if you see lock errors, close other processes using it.

---

## License

MIT License (or choose your own). You are free to use, modify, and distribute this software.

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## Disclaimer

This tool is for educational and legitimate data collection purposes only. Always respect `robots.txt`, terms of service, and applicable laws. The authors are not responsible for misuse.
