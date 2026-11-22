# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Public Reallexi website collection and portable, source-attributed datasets."""
from __future__ import annotations

from collections import deque
import csv
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import re
from pathlib import Path
import socket
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
import zipfile

AGENT = "ReallexiDatasetBuilder/1.0"
STORE_HOSTS = {"apps.apple.com", "itunes.apple.com", "play.google.com", "marketplace.visualstudio.com", "chromewebstore.google.com", "apps.microsoft.com"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".mp4", ".mp3", ".zip", ".exe", ".apk", ".dmg", ".pdf", ".woff", ".woff2", ".css", ".js"}
MAX_RESPONSE = 4 * 1024 * 1024


def reallexi_host(host):
    return host == "reallexi.io" or host.endswith(".reallexi.io")


def canonical(url, base="https://reallexi.io/"):
    try:
        parts = urlsplit(urljoin(base, str(url).strip()))
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"https", "http"} or not host or parts.username or parts.password or port not in {None, 80, 443}:
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_") and k not in {"fbclid", "gclid"}]
    # Site searches/queries must not create an unbounded crawl. Store IDs remain.
    query = query if host in STORE_HOSTS else []
    return urlunsplit(("https", host, parts.path or "/", urlencode(query), ""))


def eligible(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not (reallexi_host(host) or host in STORE_HOSTS):
        return False
    if Path(parts.path).suffix.lower() in SKIP_SUFFIXES:
        return False
    if host == "play.google.com" and parts.path != "/store/apps/details":
        return False
    if host in {"apps.apple.com", "itunes.apple.com"} and not re.search(r"/id\d+", parts.path):
        return False
    if host == "chromewebstore.google.com" and not parts.path.startswith("/detail/"):
        return False
    if host == "marketplace.visualstudio.com" and parts.path != "/items":
        return False
    return True


def public_target(url):
    parts = urlsplit(url)
    policy_url = parts.path == "/robots.txt" and parts.hostname in STORE_HOSTS
    if not (eligible(url) or policy_url):
        raise ValueError("Only public Reallexi sites and directly linked supported app stores are fetched.")
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Dataset sources must resolve to public Internet addresses.")


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = canonical(newurl, req.full_url)
        public_target(target or "")
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch(url):
    public_target(url)
    opener = build_opener(Redirects())
    with opener.open(Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/xml,text/plain"}), timeout=20) as response:
        final = canonical(response.url)
        public_target(final or "")
        content = response.read(MAX_RESPONSE + 1)
        if len(content) > MAX_RESPONSE:
            raise ValueError("Page exceeds the 4 MiB text-response budget.")
        return final, content.decode(response.headers.get_content_charset() or "utf-8", errors="replace"), response.headers.get_content_type()


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links, self.title, self.descriptions = [], [], [], []
        self.skip = 0
        self.in_title = False
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "template"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attrs.get("name", attrs.get("property", "")).lower() in {"description", "og:description"}:
            self.descriptions.append(attrs.get("content", ""))
        if tag == "a" and attrs.get("href"):
            self.anchor = {"url": attrs["href"], "label": ""}
            self.links.append(self.anchor)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
        if tag == "a":
            self.anchor = None

    def handle_data(self, data):
        if self.skip:
            return
        value = " ".join(data.split())
        if value:
            self.text.append(value)
            if self.in_title:
                self.title.append(value)
            if self.anchor is not None:
                self.anchor["label"] += value + " "


def collect(destination, seeds=(), max_pages=500, progress=lambda **kw: None, check=lambda: None, loader=fetch, delay=.2):
    """Bounded crawl. Coverage and failures are retained rather than claiming completeness."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    queue = deque(["https://reallexi.io/"])
    for seed in seeds:
        url = canonical(seed)
        if not url or not reallexi_host(urlsplit(url).hostname or ""):
            raise ValueError("Additional seeds must be reallexi.io subdomain URLs.")
        queue.append(url)
    visited, fingerprints, robots, records, links, failures, hosts = set(), set(), {}, [], {}, [], set()
    start, text_bytes = time.monotonic(), 0

    def policy(url):
        parts = urlsplit(url)
        origin = f"https://{parts.hostname}"
        if origin not in robots:
            parser = RobotFileParser(origin + "/robots.txt")
            try:
                _, body, _ = loader(parser.url)
                parser.parse(body.splitlines())
                if reallexi_host(parts.hostname):
                    queue.extend(filter(None, (canonical(item) for item in (parser.site_maps() or []))))
            except HTTPError as error:
                if error.code == 404:
                    parser.parse([])
                else:
                    parser.disallow_all = True
                    failures.append({"url": parser.url, "reason": f"robots unavailable: HTTP {error.code}; origin skipped"})
            except Exception as error:
                parser.disallow_all = True
                failures.append({"url": parser.url, "reason": f"robots unavailable: {error}; origin skipped"})
            robots[origin] = parser
            if reallexi_host(parts.hostname):
                queue.append(origin + "/sitemap.xml")
        return robots[origin].can_fetch(AGENT, url)

    while queue and len(visited) < max_pages and text_bytes < 64 * 1024 * 1024 and time.monotonic() - start < 600:
        check()
        url = queue.popleft()
        if not url or url in visited or not eligible(url):
            continue
        visited.add(url)
        progress(pages_checked=len(visited), documents=len(records), current_url=url, pending=len(queue))
        try:
            if not policy(url):
                failures.append({"url": url, "reason": "robots.txt disallows collection"})
                continue
            final, body, content_type = loader(url)
            if not final or not eligible(final):
                raise ValueError("Redirect left the allowed source scope.")
            hosts.add(urlsplit(final).hostname)
            if "xml" in content_type or body.lstrip().startswith("<?xml"):
                if reallexi_host(urlsplit(final).hostname or ""):
                    xml = ET.fromstring(body)
                    queue.extend(filter(None, (canonical(node.text or "", final) for node in xml.iter() if node.tag.rsplit("}", 1)[-1] == "loc")))
                continue
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                continue
            page = Page()
            page.feed(body)
            outgoing = []
            for item in page.links:
                target = canonical(item["url"], final)
                if not target:
                    continue
                entry = {"source_url": final, "url": target, "label": item["label"].strip(), "is_store": reallexi_host(urlsplit(final).hostname or "") and urlsplit(target).hostname in STORE_HOSTS and eligible(target)}
                links[(final, target)] = entry
                outgoing.append({"url": target, "label": entry["label"]})
                # Never walk related apps or other store navigation.
                if reallexi_host(urlsplit(final).hostname or "") and eligible(target):
                    queue.append(target)
            text = "\n".join(page.descriptions + page.text)
            digest = hashlib.sha256(" ".join(text.split()).encode()).hexdigest()
            if len(text) < 80:
                failures.append({"url": final, "reason": "Insufficient server-rendered public text; JavaScript-only content needs a separate export"})
            elif digest not in fingerprints:
                fingerprints.add(digest)
                record = {"url": final, "title": " ".join(page.title), "text": text, "links": outgoing, "sha256": digest,
                          "kind": "reallexi" if reallexi_host(urlsplit(final).hostname or "") else "app_store", "retrieved_at": time.time()}
                records.append(record)
                text_bytes += len(text.encode())
            parser = robots[f"https://{urlsplit(url).hostname}"]
            rate = parser.request_rate(AGENT)
            pause = max(delay, parser.crawl_delay(AGENT) or 0, rate.seconds / rate.requests if rate else 0)
            deadline = time.monotonic() + min(pause, max(0, 600 - (time.monotonic() - start)))
            while time.monotonic() < deadline:
                check()
                time.sleep(min(.5, max(0, deadline - time.monotonic())))
        except Exception as error:
            failures.append({"url": url, "reason": str(error)})
    if len(records) < 2:
        raise ValueError("Need at least two distinct public documents to make separate training and evaluation files. Check coverage errors and supply additional seeds.")
    # Hash order gives a reproducible document-level split; duplicates were removed before splitting.
    ordered = sorted(records, key=lambda record: record["sha256"])
    evaluation = {record["sha256"] for record in ordered[:max(1, round(len(ordered) * .1))]}
    for record in records:
        record["split"] = "evaluation" if record["sha256"] in evaluation else "train"
    for split, name in [("train", "train.txt"), ("evaluation", "evaluation.txt")]:
        with (destination / name).open("w", encoding="utf-8") as stream:
            for record in records:
                if record["split"] == split:
                    stream.write(f"Title: {record['title']}\nSource: {record['url']}\n{record['text']}\n\n")
                    if record["links"]:
                        stream.write("Links:\n" + "\n".join(f"{item['label']}: {item['url']}" for item in record["links"]) + "\n\n")
    with (destination / "documents.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (destination / "links.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_url", "url", "label", "is_store"])
        writer.writeheader()
        writer.writerows(links.values())
    apps = app_catalog(records, links.values())
    (destination / "apps.json").write_text(json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")
    pending = {url for url in queue if url and url not in visited and eligible(url)}
    coverage = {"documents": len(records), "training_documents": len(records) - len(evaluation), "evaluation_documents": len(evaluation),
                "pages_checked": len(visited), "domains": sorted(hosts), "store_links": sum(item["is_store"] for item in links.values()),
                "app_listings": len(apps), "pending_urls": len(pending), "failures": failures, "max_pages": max_pages,
                "budget_reached": bool(pending), "created_at": time.time(), "text_bytes": text_bytes,
                "scope": "Public linked Reallexi subdomains and directly linked store listings; no private/account content or DNS enumeration.",
                "rights": "Retain source attribution and source terms. Collection does not grant redistribution rights to third-party store content.",
                "split": "Deterministic 90/10 document split after exact-text deduplication; shared site boilerplate may remain."}
    coverage["files"] = {name: {"sha256": hashlib.sha256((destination / name).read_bytes()).hexdigest(), "bytes": (destination / name).stat().st_size}
                         for name in ["train.txt", "evaluation.txt", "documents.jsonl", "links.csv", "apps.json"]}
    (destination / "manifest.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    (destination / "README.md").write_text("# Reallexi public knowledge dataset\n\nUse train.txt for continual pre-training and evaluation.txt only for held-out checks. documents.jsonl preserves source records and split assignments. links.csv includes app-store URLs and their source pages. manifest.json records coverage, failures, budgets, hashes and source terms.\n\nThis is a public snapshot, not a claim of complete coverage or model quality. Review third-party terms before redistribution. Refresh by running the Reallexi website builder again; builds never overwrite earlier snapshots.\n", encoding="utf-8")
    archive = destination / "reallexi-knowledge.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in ["README.md", "manifest.json", "documents.jsonl", "links.csv", "apps.json", "train.txt", "evaluation.txt"]:
            bundle.write(destination / name, name)
    return {"coverage": coverage, "train_file": str(destination / "train.txt"), "eval_file": str(destination / "evaluation.txt"), "archive": str(archive)}


def app_catalog(records, links):
    pages = {record["url"]: record for record in records}
    def store_key(url):
        parts = urlsplit(url)
        apple_id = re.search(r"/id(\d+)", parts.path)
        return f"apple:{apple_id.group(1)}" if parts.hostname in {"apps.apple.com", "itunes.apple.com"} and apple_id else canonical(url)
    listings = {store_key(record["url"]): record for record in records if record.get("kind") == "app_store"}
    apps = {}
    for link in links:
        if not (reallexi_host(urlsplit(link["source_url"]).hostname or "") and urlsplit(link["url"]).hostname in STORE_HOSTS and eligible(link["url"])):
            continue
        record = pages.get(link["url"]) or listings.get(store_key(link["url"]), {})
        app = apps.setdefault(link["url"], {"store_url": link["url"], "source_pages": [], "source_titles": [],
                                           "listing_title": record.get("title", ""), "listing_text": record.get("text", ""),
                                           "listing_fetched": bool(record)})
        if link["source_url"] not in app["source_pages"]:
            app["source_pages"].append(link["source_url"])
            app["source_titles"].append(pages.get(link["source_url"], {}).get("title", ""))
    return list(apps.values())


def run_build(directory):
    directory = Path(directory).resolve()
    settings = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    state_path = directory / "dataset-status.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    def update(**changes):
        state.update(changes, updated_at=time.time())
        temporary = state_path.with_suffix(".new")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(state_path)
    def check():
        if (directory / "cancel").exists():
            raise InterruptedError("Dataset collection cancelled; no training was started.")
    try:
        update(status="running", message="Collecting public Reallexi pages and app-store links")
        result = collect(directory / "files", settings.get("seeds", []), settings["max_pages"], update, check)
        check()
        if settings.get("auto_train"):
            import importlib
            sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
            plugin = importlib.import_module("extensions.plugins.model-surgery.backend.plugin")
            plugin.STORE, plugin.DATA_ROOT = directory.parents[1], directory.parents[2]
            try:
                recipe = {**settings["healing_recipe"], "train_file": result["train_file"], "eval_file": result["eval_file"], "train_scope": "full"}
                result["healing_job"] = plugin.create_job(recipe, check=check)["id"]
            except Exception as error:
                result["training_blocker"] = str(error)
        update(status="completed", result=result, message="Dataset saved" + ("; full-model healing queued" if result.get("healing_job") else "; training blocked" if result.get("training_blocker") else " for reuse"))
    except Exception as error:
        update(status="cancelled" if isinstance(error, InterruptedError) else "failed", message=str(error))


if __name__ == "__main__":
    run_build(sys.argv[1])
