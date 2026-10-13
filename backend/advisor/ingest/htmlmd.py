"""HTML → clean Markdown for the main content of a page.

Keeps what a student would read (headings, paragraphs, lists, tables, document links) and
drops chrome (navigation, footers, scripts, forms, hidden elements). Tables are emitted as
Markdown tables so rows stay intact for retrieval and for the language model.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

DROP_TAGS = {
    "script", "style", "noscript", "svg", "canvas", "iframe", "form", "button", "select",
    "option", "input", "textarea", "nav", "footer", "template", "head", "link", "meta",
}
BLOCK_TAGS = {
    "p", "div", "section", "article", "aside", "main", "header", "figure", "figcaption",
    "blockquote", "address", "details", "summary", "dl", "dt", "dd", "fieldset", "legend",
    "center",
}
HIDDEN_CLASS = re.compile(r"(^|\s)(visually-hidden|sr-only|d-none|hidden|collapse-hidden)(\s|$)")
CHROME_CLASS = re.compile(
    r"(navbar|main-nav|site-header|dept-bar|breadcrumb|skip-link|cookie|back-to-top|"
    r"pagination|modal-backdrop)",
    re.I,
)
SKIP_LINK_HOSTS = ("doi.org", "dx.doi.org")


NOISE_ID = re.compile(r"(noresults|nofound|no-results|empty-state|loading)", re.I)


def _is_hidden(tag: Tag) -> bool:
    """True for elements that carry no readable knowledge.

    Inline ``display:none`` is deliberately *not* treated as hidden: tabbed UIs (for
    example the per-year scheme-of-study panels) ship every tab's content hidden except
    the active one, and that content is exactly what students ask about.
    """
    if tag.get("aria-hidden") == "true" and not tag.get_text(strip=True):
        return True
    if NOISE_ID.search(tag.get("id") or ""):
        return True
    classes = tag.get("class") or []
    cls = " ".join(classes)
    if "d-none" in classes and not re.search(r"d-(sm|md|lg|xl|xxl)-(block|flex|inline|table)", cls):
        return True
    return bool(HIDDEN_CLASS.search(cls) and "d-none" not in classes)


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("​", "")
    return re.sub(r"[ \t\r\f\v]+", " ", text)


class _Converter:
    def __init__(self, base_url: str, keep_links: bool = True):
        self.base_url = base_url
        self.keep_links = keep_links

    # ------------------------------------------------------------------ inline
    def inline(self, node) -> str:
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return _clean(str(node))
        if not isinstance(node, Tag):
            return ""
        if node.name in DROP_TAGS or _is_hidden(node):
            return ""
        if node.name == "br":
            return "\n"
        inner = "".join(self.inline(c) for c in node.children)
        if node.name in ("b", "strong") and inner.strip():
            return f"**{inner.strip()}**"
        if node.name == "a":
            return self.link(node, inner)
        if node.name == "img":
            alt = (node.get("alt") or "").strip()
            return alt if alt and len(alt) > 3 else ""
        return inner

    def link(self, node: Tag, inner: str) -> str:
        """Keep link targets only where they add information.

        Internal page links are dropped (the source URL already identifies the page and the
        markup only adds noise); document downloads and external resources are kept so the
        assistant can point students at them.
        """
        text = re.sub(r"\s+", " ", inner).strip()
        href = (node.get("href") or "").strip()
        if not self.keep_links or not href or href.startswith(("#", "javascript:", "data:")):
            return inner
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0]
            return text if addr in text else f"{text} ({addr})" if text else addr
        if href.startswith("tel:"):
            return text if href[4:] in text.replace(" ", "") else f"{text} ({href[4:]})"
        url = urljoin(self.base_url, href)
        host = (urlsplit(url).hostname or "").lower()
        path = urlsplit(url).path.lower()
        if any(h in url for h in SKIP_LINK_HOSTS) or not text:
            return inner
        is_doc = path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"))
        internal = host == (urlsplit(self.base_url).hostname or "").lower()
        if internal and not is_doc:
            return inner
        if text == url:
            return url
        return f"[{text}]({url})"

    def plain(self, node) -> str:
        """Inline text without link markup (used inside table cells)."""
        saved, self.keep_links = self.keep_links, False
        try:
            return self.inline(node)
        finally:
            self.keep_links = saved

    # ------------------------------------------------------------------ blocks
    def blocks(self, node, out: list[str], depth: int = 0) -> None:
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                t = _clean(str(child)).strip()
                if t:
                    out.append(t)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in DROP_TAGS or _is_hidden(child):
                continue
            cls = " ".join(child.get("class") or []) + " " + (child.get("id") or "")
            if CHROME_CLASS.search(cls) and child.name != "body":
                continue
            name = child.name
            if "accordion-item" in (child.get("class") or []):
                qa = self.accordion_item(child)
                if qa:
                    out.append(qa)
                continue
            if re.fullmatch(r"h[1-6]", name):
                text = re.sub(r"\s+", " ", self.inline(child)).strip()
                if text:
                    out.append("\n" + "#" * int(name[1]) + " " + text + "\n")
            elif name == "table":
                out.append(self.table(child))
            elif name in ("ul", "ol"):
                out.append(self.list(child, depth, ordered=name == "ol"))
            elif name == "pre":
                out.append("```\n" + child.get_text() + "\n```")
            elif name in BLOCK_TAGS or name in ("body", "html"):
                if self._is_leaf_block(child):
                    text = self.paragraph(child)
                    if text:
                        out.append(text)
                else:
                    self.blocks(child, out, depth)
            elif name == "hr":
                out.append("")
            else:
                text = self.paragraph(child)
                if text:
                    out.append(text)

    def accordion_item(self, item: Tag) -> str:
        """FAQ accordions: the question lives in a (normally dropped) toggle button."""
        header = item.find(class_="accordion-header") or item.find("button")
        body = item.find(class_="accordion-body") or item.find(class_="accordion-collapse")
        question = re.sub(r"\s+", " ", header.get_text(" ")).strip() if header else ""
        answer_parts: list[str] = []
        if body is not None:
            self.blocks(body, answer_parts)
        answer = "\n".join(p for p in answer_parts if p).strip()
        if not (question or answer):
            return ""
        return f"**Q: {question}**\n{answer}".strip() if question else answer

    @staticmethod
    def _is_leaf_block(tag: Tag) -> bool:
        """True if the tag only holds inline content (no nested blocks / tables / lists)."""
        for d in tag.descendants:
            if isinstance(d, Tag) and (
                d.name in BLOCK_TAGS
                or d.name in ("table", "ul", "ol", "pre", "hr")
                or re.fullmatch(r"h[1-6]", d.name)
            ):
                return False
        return True

    def paragraph(self, node) -> str:
        text = self.inline(node)
        text = re.sub(r"[ ]*\n[ ]*", "\n", text)
        text = re.sub(r"[ ]{2,}", " ", text).strip()
        return text

    def list(self, node: Tag, depth: int, ordered: bool) -> str:
        lines: list[str] = []
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            if _is_hidden(li):
                continue
            nested = [c for c in li.find_all(["ul", "ol"], recursive=False)]
            head = "".join(
                self.inline(c) for c in li.children if not (isinstance(c, Tag) and c in nested)
            )
            head = re.sub(r"\s+", " ", head).strip()
            marker = f"{i}." if ordered else "-"
            if head:
                lines.append("  " * depth + f"{marker} {head}")
            for sub in nested:
                lines.append(self.list(sub, depth + 1, sub.name == "ol"))
        return "\n".join(lines)

    def table(self, table: Tag) -> str:
        rows: list[list[str]] = []
        header_rows = 0
        for tr in table.find_all("tr"):
            if tr.find_parent("table") is not table:
                continue  # nested table: handled when encountered as its own block
            cells = []
            is_header = False
            for cell in tr.find_all(["th", "td"], recursive=False):
                if _is_hidden(cell):
                    continue
                text = re.sub(r"\s+", " ", self.plain(cell)).strip().replace("|", "/")
                span = int(cell.get("colspan", 1)) if str(cell.get("colspan", "1")).isdigit() else 1
                cells.append(text)
                cells.extend([""] * (min(span, 8) - 1))
                if cell.name == "th":
                    is_header = True
            if any(c for c in cells):
                rows.append(cells)
                if is_header and len(rows) == header_rows + 1:
                    header_rows += 1
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        caption = table.find("caption")
        md = []
        if caption:
            md.append(re.sub(r"\s+", " ", caption.get_text()).strip())
        if header_rows == 0:
            # No header row in the source: emit plain "a | b | c" lines instead of
            # inventing a header out of the first data row.
            md.extend(" | ".join(c for c in r if c) for r in rows)
            return "\n".join(md)
        head = rows[0]
        body = rows[1:]
        md.append("| " + " | ".join(head) + " |")
        md.append("|" + "|".join(["---"] * width) + "|")
        md.extend("| " + " | ".join(r) + " |" for r in body)
        return "\n".join(md)


def resolve_base(soup: BeautifulSoup, page_url: str) -> str:
    """Relative links resolve against ``<base href>`` when the page declares one."""
    base = soup.find("base", href=True)
    return urljoin(page_url, base["href"]) if base else page_url


def html_to_markdown(
    html: str, base_url: str, *, root_selector: str | None = "main-content", keep_links: bool = True
) -> tuple[str, str]:
    """Return ``(title, markdown)`` for the page's main content."""
    soup = BeautifulSoup(html, "html.parser")
    base_url = resolve_base(soup, base_url)
    title = ""
    if soup.title and soup.title.string:
        title = re.sub(r"\s+", " ", soup.title.string).strip()
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    root = None
    if root_selector:
        root = soup.find(id=root_selector) or soup.find("main")
    # Third-party (WordPress) pages: prefer the article body over the menu-laden <body>.
    root = root or soup.find("article") or soup.find(class_=re.compile(r"entry-content|post-content|page-content")) \
        or soup.find(id="content") or soup.body or soup
    out: list[str] = []
    _Converter(base_url, keep_links).blocks(root, out)
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md).strip()
    return title, md
