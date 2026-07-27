import asyncio
import json
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from bs4 import BeautifulSoup
from firecrawl import AsyncFirecrawl
from firecrawl.v2.types import ScrapeOptions

from app.config import settings

logger = structlog.get_logger()

DEFAULT_MAX_PAGES = 30
REQUEST_TIMEOUT_SECONDS = 15.0
CRAWL_DELAY_SECONDS = 0.5
FIRECRAWL_JOB_TIMEOUT_SECONDS = 240

MIN_CHUNK_CHARS = 50
MERGE_THRESHOLD_CHARS = 100
CHUNK_TARGET_MIN_CHARS = 500
CHUNK_TARGET_MAX_CHARS = 800

STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside"]
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# ── PII heuristics ────────────────────────────────────────────────────────────
# CSS class/id patterns that strongly indicate testimonial or team-bio blocks.
# Not exhaustive — intended as a best-effort guard, not a legal guarantee.
_TESTIMONIAL_CLASSES = re.compile(
    r"\b(testimonial|review|quote|rating|feedback|client[-_]?say|"
    r"what[-_]?(?:our|they|clients?)[-_]?say|star[-_]?rating)\b",
    re.IGNORECASE,
)
_TEAM_CLASSES = re.compile(
    r"\b(team[-_]?member|staff[-_]?(?:member|card|profile)?|"
    r"our[-_]?team|meet[-_]?(?:the[-_]?)?team|bio|employee[-_]?card|"
    r"doctor[-_]?card|dentist[-_]?card|attorney[-_]?card|lawyer[-_]?card)\b",
    re.IGNORECASE,
)
# Attribution line like "— Jane Smith" or "- John D." at the end of a block
_ATTRIBUTION_LINE_RE = re.compile(r"^\s*[-–—]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z.]+)*\s*$", re.MULTILINE)
# Star-rating markers (★★★★★ or 5/5 or "5 stars")
_STAR_RATING_RE = re.compile(r"[★☆]{3,}|[1-5]\s*/\s*5\b|\b[1-5]\s+stars?\b", re.IGNORECASE)

# Requires punctuation/spacing between groups (not bare digit runs) to avoid
# false-positives on order numbers, zip+4 codes, etc. — real phone numbers on
# websites are almost always written with some separator.
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_STREET_SUFFIX = (
    r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|"
    r"Circle|Cir|Place|Pl|Highway|Hwy|Parkway|Pkwy|Terrace|Ter|Trail|Trl)"
)
ADDRESS_RE = re.compile(
    rf"\d{{1,6}}\s+[A-Za-z0-9.'\s]{{2,40}}?{_STREET_SUFFIX}\.?,?\s*"
    rf"(?:(?:Suite|Ste|Unit|#)\s*[\w-]+,?\s*)?"
    rf"[A-Za-z][A-Za-z.\s]{{1,25}},\s*[A-Z]{{2}}\s*\d{{5}}(?:-\d{{4}})?",
    re.IGNORECASE,
)
_BUSINESS_JSONLD_TYPES = {"LocalBusiness", "Organization", "Dentist", "MedicalBusiness", "MedicalOrganization"}

# Self-identifying (not spoofed as a browser) — we're crawling an org's own
# site at their request, not evading anti-bot measures. Still, plenty of
# WAFs reject requests with no User-Agent at all, so this avoids spurious
# 403s from that alone.
CRAWLER_HEADERS = {"User-Agent": "AIReceptionistBot/1.0 (+knowledge-base import)"}


class CrawlError(Exception):
    pass


def _strip_pii_blocks(soup: BeautifulSoup, page_url: str) -> int:
    """Remove DOM elements that heuristically look like testimonial or team-bio
    blocks. Operates in-place on `soup`. Returns the number of blocks removed
    so callers can log the count for knowledge-base ingestion visibility.

    Matches on CSS class/id attributes — fast and low false-positive rate since
    developers use semantic names for these sections. Falls back to content
    heuristics (star ratings, attribution lines) when class names aren't helpful.
    """
    removed = 0

    for tag in soup.find_all(True):  # all elements
        cls_str = " ".join(tag.get("class") or [])
        id_str = tag.get("id") or ""
        combined = f"{cls_str} {id_str}"

        if _TESTIMONIAL_CLASSES.search(combined) or _TEAM_CLASSES.search(combined):
            tag.decompose()
            removed += 1
            continue

        # Content heuristic: a short block (<300 chars) that contains both a
        # star rating AND an attribution line is almost certainly a testimonial.
        text = tag.get_text(" ", strip=True)
        if (
            len(text) < 300
            and _STAR_RATING_RE.search(text)
            and _ATTRIBUTION_LINE_RE.search(text)
        ):
            tag.decompose()
            removed += 1

    if removed:
        logger.info("crawler_pii_blocks_stripped", url=page_url, blocks_removed=removed)

    return removed


def _markdown_has_pii_markers(text: str) -> bool:
    """Return True if a markdown chunk looks like a testimonial (star rating +
    attribution line). Used to flag Firecrawl-sourced chunks that we can't
    DOM-filter since Firecrawl already converted the HTML to markdown."""
    return bool(_STAR_RATING_RE.search(text) and _ATTRIBUTION_LINE_RE.search(text))


# ---------------------------------------------------------------------------
# PRIMARY: Firecrawl
# ---------------------------------------------------------------------------


async def crawl_website_firecrawl(url: str, max_pages: int = DEFAULT_MAX_PAGES) -> list[dict]:
    """Crawl `url` via the Firecrawl API. Raises CrawlError on any failure
    (auth, rate limit, timeout, empty result) so the router can fall back
    to the simple crawler cleanly."""
    if not settings.FIRECRAWL_API_KEY:
        raise CrawlError("Firecrawl is not configured")

    client = AsyncFirecrawl(api_key=settings.FIRECRAWL_API_KEY)
    try:
        job = await client.crawl(
            url=url,
            limit=max_pages,
            scrape_options=ScrapeOptions(formats=["markdown"], only_main_content=True),
            timeout=FIRECRAWL_JOB_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        # The SDK raises distinct types for auth/rate-limit/timeout/network
        # failures — all of them mean "fall back", so one broad catch here.
        raise CrawlError(f"Firecrawl request failed: {exc}") from exc

    if job.status != "completed":
        raise CrawlError(f"Firecrawl job did not complete (status={job.status})")

    pages = []
    for doc in job.data or []:
        if not doc.markdown:
            continue
        meta = doc.metadata
        source_url = (getattr(meta, "source_url", None) or getattr(meta, "url", None) or url) if meta else url
        title = (getattr(meta, "title", None) or source_url) if meta else source_url
        pages.append({"url": source_url, "title": title, "content": doc.markdown})

    if not pages:
        raise CrawlError("Firecrawl returned no pages")

    return pages


# ---------------------------------------------------------------------------
# CONTACT INFO — must run before nav/header/footer are stripped, since that's
# exactly where most sites put their address/phone/email on every page.
# ---------------------------------------------------------------------------


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = re.sub(r"\s+", " ", item).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(re.sub(r"\s+", " ", item).strip())
    return result


def _extract_jsonld_contact(soup: BeautifulSoup) -> dict:
    phones, emails, addresses = [], [], []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            types = item_type if isinstance(item_type, list) else [item_type]
            if not (set(types) & _BUSINESS_JSONLD_TYPES) and "address" not in item and "telephone" not in item:
                continue

            if item.get("telephone"):
                phones.append(str(item["telephone"]))
            if item.get("email"):
                emails.append(str(item["email"]))

            address = item.get("address")
            if isinstance(address, dict):
                parts = [
                    address.get("streetAddress"),
                    address.get("addressLocality"),
                    address.get("addressRegion"),
                    address.get("postalCode"),
                ]
                joined = ", ".join(str(p) for p in parts if p)
                if joined:
                    addresses.append(joined)
            elif isinstance(address, str) and address:
                addresses.append(address)

    return {"phones": phones, "emails": emails, "addresses": addresses}


def _extract_microformat_contact(soup: BeautifulSoup) -> dict:
    phones, emails, addresses = [], [], []

    for tag in soup.find_all("address"):
        text = tag.get_text(" ", strip=True)
        if text:
            addresses.append(text)

    street = soup.find(attrs={"itemprop": "streetAddress"}) or soup.find(class_="street-address")
    locality = soup.find(attrs={"itemprop": "addressLocality"}) or soup.find(class_="locality")
    region = soup.find(attrs={"itemprop": "addressRegion"}) or soup.find(class_="region")
    postal = soup.find(attrs={"itemprop": "postalCode"}) or soup.find(class_="postal-code")
    parts = [t.get_text(strip=True) for t in (street, locality, region, postal) if t]
    if parts:
        addresses.append(", ".join(parts))

    for tag in soup.find_all(attrs={"itemprop": "telephone"}) + soup.find_all(class_="tel"):
        text = tag.get_text(strip=True)
        if text:
            phones.append(text)

    for tag in soup.find_all(attrs={"itemprop": "email"}):
        text = tag.get_text(strip=True) or tag.get("content", "")
        if text:
            emails.append(text)

    # tel:/mailto: links are a strong, low-noise signal wherever they appear
    # (very often in exactly the header/footer this feature exists to save).
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            emails.append(href[len("mailto:") :].split("?")[0])
        elif href.startswith("tel:"):
            phones.append(href[len("tel:") :])

    return {"phones": phones, "emails": emails, "addresses": addresses}


def extract_contact_info(html: str, url: str) -> dict:
    """Finds phone/email/address in `html` (or Firecrawl markdown — the
    structured-markup lookups below simply find nothing on plain text, but
    the regex fallback still works on it). Combines JSON-LD schema.org
    markup, itemprop/vcard microformats, and tel:/mailto: links with a regex
    fallback over the raw text, since coverage varies wildly by site.
    """
    soup = BeautifulSoup(html, "html.parser")

    jsonld = _extract_jsonld_contact(soup)
    microformat = _extract_microformat_contact(soup)

    flat_text = soup.get_text(" ", strip=True)
    line_text = soup.get_text("\n", strip=True)

    regex_phones = PHONE_RE.findall(flat_text)
    regex_emails = EMAIL_RE.findall(flat_text)
    regex_addresses = [m.group(0) for m in ADDRESS_RE.finditer(flat_text)]

    phones = _dedupe(jsonld["phones"] + microformat["phones"] + regex_phones)
    emails = _dedupe(jsonld["emails"] + microformat["emails"] + regex_emails)
    addresses = _dedupe(jsonld["addresses"] + microformat["addresses"] + regex_addresses)

    # Best-effort fallback for when nothing structured matched but a nearby
    # line still reads as contact info (e.g. an address split across a few
    # short footer lines with no markup at all).
    contact_like_lines = [
        line.strip()
        for line in line_text.split("\n")
        if line.strip() and (PHONE_RE.search(line) or EMAIL_RE.search(line) or ADDRESS_RE.search(line))
    ]
    raw_business_info = " | ".join(_dedupe(contact_like_lines)[:5])

    return {"phones": phones, "emails": emails, "addresses": addresses, "raw_business_info": raw_business_info}


def _build_contact_chunk(contact: dict, url: str) -> dict | None:
    segments = []
    if contact["addresses"]:
        segments.append(f"Address: {'; '.join(contact['addresses'])}")
    if contact["phones"]:
        segments.append(f"Phone: {'; '.join(contact['phones'])}")
    if contact["emails"]:
        segments.append(f"Email: {'; '.join(contact['emails'])}")

    if not segments and contact.get("raw_business_info"):
        segments.append(contact["raw_business_info"])

    if not segments:
        return None

    return {"title": "Business Contact Information", "content": ". ".join(segments) + ".", "source_url": url}


async def _fetch_raw_html(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True, headers=CRAWLER_HEADERS
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        logger.warning("contact_info_homepage_fetch_failed", url=url, error=str(exc))
        return None


async def _fetch_full_page_via_firecrawl(url: str) -> str | None:
    """Same page, but without only_main_content — used as a supplemental
    fetch when the crawl's main-content-only markdown stripped the
    header/footer that usually carries contact info. Going through
    Firecrawl's own infra here (rather than a direct httpx fetch) also
    sidesteps any local SSL trust-store quirks a specific site might trigger."""
    if not settings.FIRECRAWL_API_KEY:
        return None
    try:
        client = AsyncFirecrawl(api_key=settings.FIRECRAWL_API_KEY)
        doc = await client.scrape(url=url, formats=["markdown"], only_main_content=False)
        return doc.markdown
    except Exception as exc:
        logger.warning("contact_info_full_page_scrape_failed", url=url, error=str(exc))
        return None


def _merge_contact(contacts: list[dict]) -> dict:
    phones, emails, addresses, raw_infos = [], [], [], []
    for c in contacts:
        phones += c["phones"]
        emails += c["emails"]
        addresses += c["addresses"]
        if c["raw_business_info"]:
            raw_infos.append(c["raw_business_info"])
    return {
        "phones": _dedupe(phones),
        "emails": _dedupe(emails),
        "addresses": _dedupe(addresses),
        "raw_business_info": " | ".join(_dedupe(raw_infos)[:5]),
    }


def _has_any_contact(contact: dict) -> bool:
    return bool(contact["phones"] or contact["emails"] or contact["addresses"])


async def _extract_site_contact_info(provider: str, pages: list[dict], url: str) -> dict:
    empty = {"phones": [], "emails": [], "addresses": [], "raw_business_info": ""}
    if not pages:
        return empty

    # Cheap first pass, no extra network calls: scan every already-fetched
    # page — contact info sometimes survives on a page other than the
    # homepage, or in a per-page footer fragment that only_main_content
    # didn't fully strip.
    contact = _merge_contact([extract_contact_info(page["content"], page["url"]) for page in pages])
    if _has_any_contact(contact):
        return contact

    # Nothing on any crawled page. One supplemental fetch of the homepage
    # itself without the main-content filter, in case its own header/footer
    # (stripped from the crawl) carries it.
    if provider == "firecrawl":
        markdown = await _fetch_full_page_via_firecrawl(url)
        if markdown:
            supplemental = extract_contact_info(markdown, url)
            if _has_any_contact(supplemental):
                return supplemental

    html = await _fetch_raw_html(url)
    return extract_contact_info(html, url) if html else contact


# ---------------------------------------------------------------------------
# FALLBACK: httpx + BeautifulSoup
# ---------------------------------------------------------------------------


async def _load_robots_parser(client: httpx.AsyncClient, scheme: str, domain: str) -> RobotFileParser:
    parser = RobotFileParser()
    robots_url = f"{scheme}://{domain}/robots.txt"
    parser.set_url(robots_url)
    try:
        response = await client.get(robots_url)
        parser.parse(response.text.splitlines() if response.status_code == 200 else [])
    except httpx.HTTPError:
        parser.parse([])
    return parser


def _extract_text(soup: BeautifulSoup) -> str:
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return "\n".join(t.strip() for t in main.stripped_strings if t.strip())


async def crawl_website_simple(url: str, max_pages: int = DEFAULT_MAX_PAGES) -> list[dict]:
    root = urlparse(url)
    domain = root.netloc

    pages: list[dict] = []
    visited: set[str] = set()
    queue: list[str] = [url]

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True, headers=CRAWLER_HEADERS
    ) as client:
        robots = await _load_robots_parser(client, root.scheme, domain)

        while queue and len(pages) < max_pages:
            current = queue.pop(0)
            normalized = current.split("#")[0].rstrip("/")
            if normalized in visited:
                continue
            visited.add(normalized)

            if not robots.can_fetch("*", current):
                continue

            try:
                response = await client.get(current)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("crawl_page_failed", url=current, error=str(exc))
                continue

            if "text/html" not in response.headers.get("content-type", ""):
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup.find_all(STRIP_TAGS):
                tag.decompose()
            _strip_pii_blocks(soup, current)

            title = soup.title.get_text(strip=True) if soup.title else current
            text = _extract_text(soup)
            if text:
                pages.append({"url": current, "title": title, "content": text})

            for link in soup.find_all("a", href=True):
                href = urljoin(current, link["href"]).split("#")[0]
                parsed_link = urlparse(href)
                normalized_href = href.rstrip("/")
                if (
                    parsed_link.netloc == domain
                    and parsed_link.scheme in ("http", "https")
                    and normalized_href not in visited
                    and href not in queue
                ):
                    queue.append(href)

            await asyncio.sleep(CRAWL_DELAY_SECONDS)

    return pages


# ---------------------------------------------------------------------------
# CHUNKER
# ---------------------------------------------------------------------------


def _split_by_headings(content: str) -> list[tuple[str | None, str]]:
    matches = list(HEADING_RE.finditer(content))
    if not matches:
        return [(None, content)]

    sections: list[tuple[str | None, str]] = []
    preamble = content[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))

    for i, match in enumerate(matches):
        heading_text = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if body:
            sections.append((heading_text, body))

    return sections


def _split_by_length(text: str) -> list[str]:
    if len(text) <= CHUNK_TARGET_MAX_CHARS:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    # A "paragraph" with no internal blank lines (e.g. a wall-of-text page
    # with no markdown structure) would otherwise pass through as one
    # oversized unit — break it on sentence boundaries first.
    units: list[str] = []
    for para in paragraphs:
        if len(para) > CHUNK_TARGET_MAX_CHARS:
            units.extend(s.strip() for s in SENTENCE_SPLIT_RE.split(para) if s.strip())
        else:
            units.append(para)

    pieces: list[str] = []
    buffer = ""
    for unit in units:
        candidate = f"{buffer} {unit}".strip() if buffer else unit
        if len(candidate) > CHUNK_TARGET_MAX_CHARS and buffer:
            pieces.append(buffer)
            buffer = unit
        else:
            buffer = candidate
            if len(buffer) >= CHUNK_TARGET_MIN_CHARS:
                pieces.append(buffer)
                buffer = ""
    if buffer:
        pieces.append(buffer)
    return pieces


def _merge_short_chunks(chunks: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for chunk in chunks:
        if merged and len(merged[-1]["content"]) < MERGE_THRESHOLD_CHARS:
            merged[-1]["content"] = f"{merged[-1]['content']}\n\n{chunk['content']}"
        else:
            merged.append(dict(chunk))
    return merged


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Heading/length-based chunking only — the "Business Contact
    Information" chunk is built separately by crawl_website and prepended
    there, so it isn't duplicated if a page's own heading structure happens
    to also produce a contact-ish chunk."""
    raw_chunks: list[dict] = []

    for page in pages:
        for heading, body in _split_by_headings(page["content"]):
            for piece in _split_by_length(body):
                piece = piece.strip()
                if not piece:
                    continue
                title = f"{page['title']} - {heading}" if heading else page["title"]
                raw_chunks.append({"title": title, "content": piece, "source_url": page["url"]})

    long_enough = [c for c in raw_chunks if len(c["content"]) >= MIN_CHUNK_CHARS]

    # Drop chunks that look like testimonials in markdown (star rating +
    # attribution line). Logs each skip so it's visible in ingestion output.
    clean: list[dict] = []
    for chunk in long_enough:
        if _markdown_has_pii_markers(chunk["content"]):
            logger.info(
                "crawler_pii_chunk_skipped",
                title=chunk.get("title"),
                source_url=chunk.get("source_url"),
                chars=len(chunk["content"]),
            )
        else:
            clean.append(chunk)

    return _merge_short_chunks(clean)


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------


async def crawl_website(url: str, max_pages: int = DEFAULT_MAX_PAGES) -> dict:
    pages: list[dict] = []
    provider = "fallback"

    if settings.FIRECRAWL_API_KEY:
        try:
            pages = await crawl_website_firecrawl(url, max_pages)
            provider = "firecrawl"
        except CrawlError as exc:
            logger.warning("firecrawl_failed_falling_back", url=url, error=str(exc))

    if not pages:
        pages = await crawl_website_simple(url, max_pages)
        provider = "fallback"

    chunks = chunk_pages(pages)

    contact = await _extract_site_contact_info(provider, pages, url)
    contact_chunk = _build_contact_chunk(contact, url)
    if contact_chunk:
        chunks.insert(0, contact_chunk)
        logger.info(
            "contact_info_extracted",
            url=url,
            phones=contact["phones"],
            emails=contact["emails"],
            addresses=contact["addresses"],
        )
    else:
        logger.warning("contact_info_not_found", url=url)

    return {"provider": provider, "pages_crawled": len(pages), "chunks": chunks}
