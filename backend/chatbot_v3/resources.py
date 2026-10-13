"""Links observed in source documents, never links invented by a generator."""

from urllib.parse import parse_qs, urldefrag, urlencode, urljoin, urlsplit, urlunsplit

OFFICIAL_HOSTS = {"cs.qau.edu.pk", "qau.edu.pk", "www.qau.edu.pk"}


def public_resource_url(value, base=""):
    try:
        url = urljoin(base, value or "")
        u = urlsplit(url)
        port = u.port
    except ValueError:
        return None
    if (
        u.scheme not in {"https", "http"}
        or u.hostname not in OFFICIAL_HOSTS
        or u.username
        or u.password
        or port not in {None, 80, 443}
        or any(w in u.path.lower() for w in ["login", "logout", "wp-admin", "signin"])
    ):
        return None
    # Download Manager's public numeric GET identifies a file, not a form action.
    if u.query:
        query = parse_qs(u.query)
        if (
            not set(query) <= {"wpdmdl", "refresh"}
            or "wpdmdl" not in query
            or len(query["wpdmdl"]) != 1
            or not query["wpdmdl"][0].isdigit()
        ):
            return None
        stable_query = urlencode({"wpdmdl": query["wpdmdl"][0]})
    else:
        stable_query = ""
    return urlunsplit(("https", u.hostname, u.path or "/", stable_query, u.fragment))


def source_links(node, base):
    result, seen = [], set()
    anchors = ([node] if node.get("href") or node.get("data-downloadurl") else []) + node.select(
        "a[href], [data-downloadurl]"
    )
    for anchor in anchors:
        raw = anchor.get("data-downloadurl") or anchor.get("href")
        if not raw or raw.startswith("#"):
            continue
        url = public_resource_url(raw, base)
        title = anchor.get_text(" ", strip=True) or anchor.get("title") or anchor.get("aria-label")
        if title and title.casefold() in {"download", "pdf", "click here"}:
            for parent in anchor.parents:
                if getattr(parent, "name", None) in {"main", "body", "html"}:
                    break
                heading = parent.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                if heading:
                    title = heading.get_text(" ", strip=True) + " — " + title
                    break
        if url and title and url not in seen and urldefrag(url)[0] != urldefrag(base)[0]:
            seen.add(url)
            result.append({"title": title[:240], "url": url})
    return result[:80]
