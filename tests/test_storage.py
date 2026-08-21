from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
import shutil
from crawler.settings import Settings
from crawler.storage import FileManager


class TestFileManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            output_dir=str(Path(self.tmpdir.name) / "out"),
            output_formats=["jsonl", "sqlite"],
            batch_size=2,
        )
        self.fm = FileManager(self.settings)
        await self.fm.init_sqlite()

    async def asyncTearDown(self):
        await self.fm.flush_batch()
        self.tmpdir.cleanup()

    async def test_add_and_flush(self):
        page = {
            "url": "http://example.com",
            "title": "Test",
            "content": "Hello",
            "quality_score": 5,
            "depth": 0,
            "domain": "example.com",
            "content_hash": "abc",
            "timestamp": "2024-01-01",
        }
        await self.fm.add_page(page)
        await self.fm.flush_batch()
        files = self.fm.list_files()
        self.assertTrue(any(f.endswith("pages.jsonl") for f in files))
        self.assertTrue(any(f.endswith("crawled_pages.db") for f in files))

    async def test_compress(self):
        await self.fm.add_page({
            "url": "http://example.com", "title": "", "content": "",
            "quality_score": 1, "depth": 0, "domain": "example.com",
            "content_hash": "", "timestamp": "",
        })
        await self.fm.flush_batch()
        archive = await self.fm.compress_output("test_archive")
        self.assertTrue(Path(archive).exists())

    async def test_delete(self):
        path = Path(self.settings.output_dir) / "dummy.txt"
        path.write_text("hello")
        self.fm.delete_file(str(path))
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()