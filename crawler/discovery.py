from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from selectolax.parser import HTMLParser


def parse_sitemap(content: str | bytes) -> tuple[list[str], list[str]]:
    """
    Parse a sitemap XML document.

    Returns:
        (page_urls, nested_sitemap_urls)

    If the document is a sitemap index, page_urls is empty and
    nested_sitemap_urls contains the child sitemap URLs.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    page_urls: list[str] = []
    nested_sitemap_urls: list[str] = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        # Fallback regex: still extract <loc> entries from malformed XML
        text = content.decode("utf-8", errors="ignore")
        urls = re.findall(r"<loc[^>]*>(.*?)</loc>", text, re.I | re.S)
        # Can't tell if it was an index; assume all are page URLs
        return [u.strip() for u in urls if u.strip()], []

    root_tag = root.tag.split("}")[-1]
    for elem in root.iter():
        if elem.tag.split("}")[-1] != "loc":
            continue
        if not elem.text:
            continue
        url = elem.text.strip()
        if root_tag == "sitemapindex":
            nested_sitemap_urls.append(url)
        else:
            page_urls.append(url)

    return page_urls, nested_sitemap_urls


def extract_links_from_html(parser: HTMLParser, base_url: str) -> set[str]:
    """
    Extract all internal/page URLs from a parsed HTML document.

    Covers:
      - Anchor tags (<a href>)
      - iframe src
      - meta refresh
      - canonical link
      - JSON-LD script URLs
      - Next.js __NEXT_DATA__ and other embedded JSON scripts
    """
    links: set[str] = set()

    def _add(url: str) -> None:
        candidate = url.strip()
        if not candidate:
            return
        abs_url = urljoin(base_url, candidate)
        if abs_url.startswith(("http://", "https://")):
            links.add(abs_url)

    # Anchor links
    for a in parser.css("a[href]"):
        href = a.attributes.get("href")
        if href:
            _add(href)

    # iframe
    for node in parser.css("iframe[src]"):
        src = node.attributes.get("src")
        if src:
            _add(src)

    # meta refresh
    for meta in parser.css("meta[http-equiv='refresh']"):
        content = meta.attributes.get("content", "")
        match = re.search(r"url\s*=\s*[\"']?([^\"'>\s]+)", content, re.I)
        if match:
            _add(match.group(1))

    # canonical
    for link in parser.css("link[rel='canonical']"):
        href = link.attributes.get("href")
        if href:
            _add(href)

    # JSON-LD and embedded JSON (Next.js, etc.)
    script_selectors = [
        "script[type='application/ld+json']",
        "script[type='application/json']",
        "script#__NEXT_DATA__",
    ]
    for selector in script_selectors:
        for script in parser.css(selector):
            text = script.text(strip=True)
            if not text:
                continue
            try:
                data = json.loads(text)
                _walk_json_urls(data, _add)
            except json.JSONDecodeError:
                # Fallback regex for common JSON link patterns
                patterns = [
                    r"[\"'](?:url|href|as|path|canonical)[\"']\s*:\s*[\"']([^\"']+)",
                    r"[\"'](?:internalUrl|pageUrl|linkUrl)[\"']\s*:\s*[\"']([^\"']+)",
                ]
                for pattern in patterns:
                    for match in re.finditer(pattern, text, re.I):
                        _add(match.group(1))

    return links


def _walk_json_urls(obj: object, add_url) -> None:
    """
    Recursively walk a decoded JSON object and extract URL-like strings.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and key.lower() in {
                "url",
                "href",
                "as",
                "path",
                "link",
                "canonical",
                "internalurl",
                "pageurl",
                "linkurl",
            }:
                add_url(value)
            _walk_json_urls(value, add_url)
    elif isinstance(obj, list):
        for item in obj:
            _walk_json_urls(item, add_url)