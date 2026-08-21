from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import aiofiles
import aiosqlite


class FileManager:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.batch: list[dict[str, Any]] = []
        self.lock = asyncio.Lock()
        self.db_path = self.output_dir / "crawled_pages.db"
        self._setup_logging()

    def _setup_logging(self) -> None:
        logger = logging.getLogger("crawler")
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            self.settings.log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

    def log_error(self, message: str) -> None:
        logging.getLogger("crawler").error(message)

    async def init_sqlite(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    quality_score INTEGER,
                    depth INTEGER,
                    domain TEXT,
                    content_hash TEXT,
                    timestamp TEXT
                )
                """
            )
            await db.commit()

    async def add_page(self, page: dict[str, Any]) -> None:
        async with self.lock:
            self.batch.append(page)
            if len(self.batch) >= self.settings.batch_size:
                await self.flush_batch()

    async def flush_batch(self) -> None:
        if not self.batch:
            return
        batch = self.batch
        self.batch = []
        if "jsonl" in self.settings.output_formats:
            await self._write_jsonl(batch)
        if "json" in self.settings.output_formats:
            await self._write_json(batch)
        if "csv" in self.settings.output_formats:
            await self._write_csv(batch)
        if "sqlite" in self.settings.output_formats:
            await self._write_sqlite(batch)

    async def _write_jsonl(self, batch: list[dict[str, Any]]) -> None:
        path = self.output_dir / "pages.jsonl"
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            for page in batch:
                await f.write(json.dumps(page, ensure_ascii=False) + "\n")

    async def _write_json(self, batch: list[dict[str, Any]]) -> None:
        path = self.output_dir / "pages.json"
        existing = []
        if path.exists():
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                existing = json.loads(await f.read())
        existing.extend(batch)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(existing, ensure_ascii=False, indent=2))

    async def _write_csv(self, batch: list[dict[str, Any]]) -> None:
        path = self.output_dir / "pages.csv"
        new_file = not path.exists()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._csv_sync, path, batch, new_file)

    def _csv_sync(self, path: Path, batch: list[dict[str, Any]], new_file: bool) -> None:
        fieldnames = ["url", "title", "content", "quality_score", "depth", "domain", "content_hash", "timestamp"]
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if new_file:
                writer.writeheader()
            for page in batch:
                writer.writerow({k: page.get(k, "") for k in fieldnames})

    async def _write_sqlite(self, batch: list[dict[str, Any]]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT INTO pages (url, title, content, quality_score, depth, domain, content_hash, timestamp)
                VALUES (:url, :title, :content, :quality_score, :depth, :domain, :content_hash, :timestamp)
                """,
                batch,
            )
            await db.commit()

    async def compress_output(self, archive_name: str | None = None) -> str:
        if not archive_name:
            archive_name = self.output_dir.name
        archive_path = self.output_dir.parent / f"{archive_name}.zip"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, shutil.make_archive, str(archive_path.with_suffix("")), "zip", str(self.output_dir))
        return str(archive_path)

    def list_files(self) -> list[str]:
        return [str(p) for p in self.output_dir.iterdir() if p.is_file()]

    def delete_file(self, filepath: str) -> None:
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    def preview_file(self, filepath: str, limit: int = 5000) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(limit)
        except Exception:
            return ""