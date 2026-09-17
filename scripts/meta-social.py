#!/usr/bin/env python3
"""Publish Iguana Comedy events to the Facebook Page and to Instagram from the command line.

Operator tool, run by hand from the dev box, like scripts/meta-ads.py. It reads the system-user token from
~/.credentials/meta/iguanacomedy/token (set META_TOKEN_FILE to point somewhere else) and never prints it, nor the
Page access token it derives from it.

    scripts/meta-social.py whoami                          can the token see the Page and IG, and publish to both
    scripts/meta-social.py recent                          last 5 Page posts and last 5 IG media, with permalinks
    scripts/meta-social.py draft <slug> [--lang both]      print exactly what would be posted, and validate it
    scripts/meta-social.py post <slug> --to both --confirm publish (without --confirm it only drafts, exit 2)

Events come from the public API the site uses. The public key is read from --api-key, then the
IGUANA_PUBLIC_API_KEY environment variable, then over ssh from the production config (never printed).

Captions are in the brand's voice ("Iguana Comedy"), bilingual by default (Spanish first for Spanish shows),
and contain no em or en dashes. Instagram links are not clickable, so the Instagram caption says "link in bio"
and carries no URL; the bio link is https://www.iguanacomedy.com/events.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v21.0"
PAGE_ID = "122106930026005410"              # Iguana Comedy Productions
INSTAGRAM_ID = "17841461594533193"          # @iguanacomedy
TOKEN_FILE = os.environ.get("META_TOKEN_FILE", "~/.credentials/meta/iguanacomedy/token")
NEEDED_SCOPES = ("pages_manage_posts", "pages_read_engagement", "instagram_basic", "instagram_content_publish")

SITE = "https://iguanacomedy.com"
EVENTS_API = os.environ.get("IGUANA_API_BASE", "https://api.iguanacomedy.com") + "/api/public/v1/events"
SSH_HOST = "iguana@38.86.78.36"
SSH_KEY_COMMAND = "grep -oE \"PUBLIC_API_KEYS = \\['[^']+\" /home/www/iguana/backend/config.py | cut -d\"'\" -f2"
DEFAULT_VENUE = "Iguana Comedy, Playa del Carmen"

# Instagram's documented limits for a feed image published through the API.
IG_MIN_RATIO, IG_MAX_RATIO = 4 / 5, 1.91
IG_MAX_BYTES = 8 * 1024 * 1024
IG_MIN_WIDTH = 320
IG_CAPTION_MAX = 2200
IG_HASHTAG_MAX = 30

DASHES = re.compile("[\u2012\u2013\u2014\u2015\u2212]")
SPACED_DASH = re.compile(r"\s+[-\u2012\u2013\u2014\u2015]+\s+")


class GraphError(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------
# Graph API


def token() -> str:
    path = pathlib.Path(TOKEN_FILE).expanduser()
    try:
        value = path.read_text().strip()
    except OSError as exc:
        # Fail loudly: an empty token turns every call into an opaque 190 instead of naming the cause.
        sys.exit(f"cannot read the Meta token from {path}: {exc}")
    if not value:
        sys.exit(f"{path} is empty; put the system-user token there (chmod 600)")
    return value


def _graph(method: str, path: str, access_token: str | None, params: dict) -> dict:
    # The token travels in the Authorization header (GET) or the form body (POST), never in a URL that an
    # exception or a proxy log could echo.
    headers = {"Authorization": f"Bearer {access_token or token()}"}
    query = urllib.parse.urlencode(params)
    if method == "GET":
        request = urllib.request.Request(f"{API}/{path}" + (f"?{query}" if query else ""), headers=headers)
    else:
        request = urllib.request.Request(f"{API}/{path}", data=query.encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            error = json.loads(body)["error"]
            parts = [error.get("message", "")]
            for key in ("code", "error_subcode", "error_user_title", "error_user_msg", "fbtrace_id"):
                if error.get(key):
                    parts.append(f"{key}={error[key]}")
            message = "; ".join(parts)
        except Exception:
            message = body[:300]
        raise GraphError(f"Graph API {exc.code} on {method} {path.split('?')[0]}: {message}") from None
    except urllib.error.URLError as exc:
        raise GraphError(f"cannot reach the Graph API for {path.split('?')[0]}: {exc.reason}") from None


def get(path: str, access_token: str | None = None, **params) -> dict:
    return _graph("GET", path, access_token, params)


def post(path: str, access_token: str | None = None, **params) -> dict:
    return _graph("POST", path, access_token, params)


def page_token() -> str:
    value = get(PAGE_ID, fields="access_token").get("access_token")
    if not value:
        raise GraphError(f"GET {PAGE_ID}?fields=access_token returned no Page token: the system user is not "
                         "assigned to the Page, or lacks pages_show_list / pages_manage_posts")
    return value


# ---------------------------------------------------------------------------------------------------------------
# Events API


def public_api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("IGUANA_PUBLIC_API_KEY")
    if key:
        return key.strip()
    try:
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", SSH_HOST, SSH_KEY_COMMAND],
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"no --api-key / IGUANA_PUBLIC_API_KEY, and reading it over ssh from {SSH_HOST} failed: {exc}")
    key = result.stdout.strip()
    if result.returncode != 0 or not key:
        sys.exit(f"no --api-key / IGUANA_PUBLIC_API_KEY, and reading PUBLIC_API_KEYS over ssh from {SSH_HOST} "
                 f"failed (exit {result.returncode}): {result.stderr.strip()[:200]}")
    return key


def fetch_event(slug: str, api_key: str) -> dict:
    url = f"{EVENTS_API}/{urllib.parse.quote(slug)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            sys.exit(f"no public event with slug {slug!r} ({url} returned 404)")
        sys.exit(f"events API {exc.code} on {url}: {exc.read().decode(errors='replace')[:200]}")
    except urllib.error.URLError as exc:
        sys.exit(f"cannot reach the events API at {url}: {exc.reason}")
    event = payload.get("event")
    if not event:
        sys.exit(f"{url} answered without an 'event' object")
    return event


# ---------------------------------------------------------------------------------------------------------------
# Captions (pure, unit-tested in scripts/tests/test_meta_social.py)

WEEKDAYS = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
}
MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"),
}
HASHTAGS = {
    "en": ("#PlayaDelCarmen", "#StandUp", "#ComedyClub"),
    "es": ("#PlayaDelCarmen", "#StandUp", "#Comedia", "#ComediaEnVivo"),
}


def is_open_mic(event: dict) -> bool:
    return "open-mic" in (event.get("tags") or [])


def event_url(event: dict, lang: str) -> str:
    slug = urllib.parse.quote(event["slug"])
    return f"{SITE}/es/eventos/{slug}/" if lang == "es" else f"{SITE}/en/events/{slug}/"


def clean_text(text: str) -> str:
    """Event names come from the admin: 'Noche de Open Mic - Espanol!' becomes 'Noche de Open Mic: Espanol!'."""
    text = SPACED_DASH.sub(": ", text.strip())
    return DASHES.sub(", ", text)


def format_time(hhmm: str | None, lang: str) -> str | None:
    if not hhmm:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", hhmm.strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if lang == "es":
        return f"{hour:02d}:{minute:02d} h"
    suffix = "AM" if hour < 12 else "PM"
    twelve = hour % 12 or 12
    return f"{twelve} {suffix}" if minute == 0 else f"{twelve}:{minute:02d} {suffix}"


def format_date(iso: str, lang: str) -> str:
    day = dt.date.fromisoformat(iso[:10])
    weekday, month = WEEKDAYS[lang][day.weekday()], MONTHS[lang][day.month - 1]
    if lang == "es":
        return f"{weekday.capitalize()} {day.day} de {month}"
    return f"{weekday}, {month} {day.day}"


def format_price(minor_units: int | None, currency: str | None) -> str | None:
    if minor_units is None:
        return None
    major = minor_units / 100
    amount = f"{major:,.0f}" if major == int(major) else f"{major:,.2f}"
    return f"{amount} {(currency or 'MXN').upper()}"


def when_line(event: dict, lang: str) -> str:
    line = format_date(event["date"], lang)
    show, doors = format_time(event.get("showTime"), lang), format_time(event.get("doorsOpen"), lang)
    if doors and show:
        line += f", puertas {doors}, show {show}" if lang == "es" else f", doors {doors}, show {show}"
    elif show:
        line += f", {show}"
    return line


def price_line(event: dict, lang: str) -> str | None:
    price = format_price(event.get("priceFrom"), event.get("priceCurrency"))
    if is_open_mic(event):
        if lang == "es":
            return "Entrada libre. Reserva tu lugar" + (f" por {price}" if price else "") + " con bebida gratis."
        return "Free entry. Reserve a seat" + (f" for {price}" if price else "") + " and get a free drink."
    if event.get("priceFrom") == 0:
        return "Entrada libre." if lang == "es" else "Free entry."
    if price:
        return f"Boletos desde {price}." if lang == "es" else f"Tickets from {price}."
    return None  # no ticket price published yet: the Tickets line below says enough


def venue_line(event: dict) -> str:
    venue = event.get("venue") or {}
    name, city = (venue.get("name") or "").strip(), (venue.get("city") or event.get("city") or "").strip()
    if name and city:
        return clean_text(name if city.lower() in name.lower() else f"{name}, {city}")
    return DEFAULT_VENUE


def language_note(event: dict, lang: str) -> str | None:
    show_lang = event.get("language") or "en"
    if show_lang == lang:
        return None
    if lang == "es":
        return "Show en inglés." if show_lang == "en" else "Show en español."
    return "Show in Spanish." if show_lang == "es" else "Show in English."


def caption_block(event: dict, lang: str, platform: str) -> str:
    lines = [clean_text(event["name"]), when_line(event, lang), venue_line(event)]
    lines += [line for line in (price_line(event, lang), language_note(event, lang)) if line]
    label = ("Reserva" if is_open_mic(event) else "Boletos") if lang == "es" else (
        "Reserve" if is_open_mic(event) else "Tickets")
    if platform == "instagram":
        lines.append(f"{label}: link en la bio" if lang == "es" else f"{label}: link in bio")
    else:
        lines.append(f"{label}: {event_url(event, lang)}")
    return "\n".join(lines)


def caption_languages(event: dict, mode: str) -> list[str]:
    if mode in ("en", "es"):
        return [mode]
    return ["es", "en"] if event.get("language") == "es" else ["en", "es"]


def build_caption(event: dict, mode: str, platform: str) -> str:
    """The full caption for one platform. mode is en, es or both; platform is facebook or instagram."""
    languages = caption_languages(event, mode)
    blocks = [caption_block(event, lang, platform) for lang in languages]
    tags: list[str] = []
    for tag in [t for lang in languages for t in HASHTAGS[lang]] + (["#OpenMic"] if is_open_mic(event) else []):
        if tag not in tags:
            tags.append(tag)
    caption = "\n\n* * *\n\n".join(blocks) + "\n\n" + " ".join(tags)
    if DASHES.search(caption):  # the brand rule, enforced rather than hoped for
        raise ValueError("caption contains an em or en dash")
    return caption


def caption_problems(caption: str, platform: str) -> list[str]:
    problems = []
    if platform == "instagram":
        if len(caption) > IG_CAPTION_MAX:
            problems.append(f"Instagram caption is {len(caption)} characters, the limit is {IG_CAPTION_MAX}")
        if caption.count("#") > IG_HASHTAG_MAX:
            problems.append(f"Instagram allows at most {IG_HASHTAG_MAX} hashtags")
        if re.search(r"https?://", caption):
            problems.append("Instagram caption contains a raw URL (links are not clickable there)")
    return problems


# ---------------------------------------------------------------------------------------------------------------
# Images (pure parser, unit-tested)

JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_dimensions(data: bytes) -> tuple[str, int, int]:
    """Return (format, width, height) from PNG or JPEG bytes. Raises ValueError for anything else."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise ValueError("truncated PNG header")
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                raise ValueError(f"corrupt JPEG: expected a marker at byte {i}")
            marker = data[i + 1]
            if marker == 0xFF:          # fill byte
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # standalone markers, no length
                i += 2
                continue
            if marker in (0xD9, 0xDA):
                break                   # end of image or start of scan before any frame header
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in JPEG_SOF:
                if i + 9 > len(data):
                    break
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", width, height
            i += 2 + length
        raise ValueError("JPEG has no frame header (SOF) before the image data")
    raise ValueError("not a PNG or JPEG")


def ratio_problem(width: int, height: int) -> str | None:
    if not width or not height:
        return f"image reports {width}x{height}"
    ratio = width / height
    if ratio < IG_MIN_RATIO - 0.005:
        return f"{width}x{height} is taller than Instagram allows (ratio {ratio:.2f}, minimum 0.80 = 4:5)"
    if ratio > IG_MAX_RATIO + 0.005:
        return f"{width}x{height} is wider than Instagram allows (ratio {ratio:.2f}, maximum 1.91:1)"
    return None


def check_image(url: str | None) -> tuple[list[str], list[str], str]:
    """Download the image the way Meta will and return (errors, warnings, summary)."""
    if not url:
        return ["the event has no image; Instagram requires one, so nothing can be posted "
                "(add an image to the event in the admin, or pass --image https://...)"], [], "none"
    if not url.lower().startswith("https://"):
        return [f"image URL is not https: {url}"], [], url
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "iguana-meta-social/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(20 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        return [f"image is not publicly reachable: {url} returned HTTP {exc.code}"], [], url
    except urllib.error.URLError as exc:
        return [f"image is not publicly reachable: {url}: {exc.reason}"], [], url
    errors, warnings = [], []
    try:
        kind, width, height = image_dimensions(data)
    except ValueError as exc:
        return [f"image at {url} is unusable: {exc} (Content-Type {content_type or 'missing'})"], [], url
    if kind not in content_type.lower():
        warnings.append(f"server says Content-Type {content_type or 'missing'} but the bytes are {kind.upper()}")
    problem = ratio_problem(width, height)
    if problem:
        errors.append(problem)
    if width < IG_MIN_WIDTH:
        errors.append(f"image is {width}px wide; Instagram needs at least {IG_MIN_WIDTH}px")
    if len(data) > IG_MAX_BYTES:
        errors.append(f"image is {len(data) / 1048576:.1f} MB; Instagram's limit is 8 MB")
    if kind == "png":
        warnings.append("Meta documents JPEG as the only image format for Instagram publishing; "
                        "if Instagram rejects this PNG, upload a JPEG to the event")
    summary = f"{kind.upper()} {width}x{height} (ratio {width / height:.2f}), {len(data) / 1024:.0f} KB"
    return errors, warnings, summary


def check_link(url: str) -> str | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "iguana-meta-social/1.0"}),
                                    timeout=30) as response:
            return None if response.status == 200 else f"{url} returned HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return f"event page {url} returned HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return f"event page {url} is unreachable: {exc.reason}"


# ---------------------------------------------------------------------------------------------------------------
# Commands


def cmd_whoami(args) -> None:
    problems: list[str] = []

    def attempt(label: str, call):
        try:
            return call()
        except GraphError as exc:
            problems.append(f"{label}: {exc}")
            print(f"  {label:10} FAILED ({exc})")
            return None

    me = attempt("token", lambda: get("me", fields="id,name"))
    if me:
        print(f"  {'token':10} system user {me.get('name')} ({me.get('id')})")

    debug = attempt("scopes", lambda: get("debug_token", input_token=token()).get("data", {}))
    if debug is not None:
        if not debug.get("is_valid"):
            problems.append(f"token is not valid: {debug.get('error', {}).get('message', 'no reason given')}")
        expires = debug.get("expires_at") or 0
        print(f"  {'expires':10} {'never' if not expires else dt.datetime.fromtimestamp(expires).isoformat()}")
        scopes = set(debug.get("scopes") or [])
        granular = {g["scope"]: g.get("target_ids") for g in debug.get("granular_scopes") or []}
        for scope in NEEDED_SCOPES:
            if scope not in scopes:
                problems.append(f"missing permission {scope}")
                print(f"  {'scope':10} {scope:28} MISSING")
                continue
            targets = granular.get(scope)
            asset = INSTAGRAM_ID if scope.startswith("instagram") else PAGE_ID
            if targets and asset not in targets:
                problems.append(f"{scope} is granted but not for asset {asset} (only {', '.join(targets)})")
                print(f"  {'scope':10} {scope:28} granted, but NOT for {asset}")
            else:
                print(f"  {'scope':10} {scope:28} ok")

    page = attempt("page", lambda: get(PAGE_ID, fields="name,username,link,instagram_business_account{id,username}"))
    if page:
        print(f"  {'page':10} {page.get('name')} (@{page.get('username')}) {page.get('link')}")
        linked = (page.get("instagram_business_account") or {}).get("id")
        if linked != INSTAGRAM_ID:
            problems.append(f"the Page's linked Instagram account is {linked}, expected {INSTAGRAM_ID}")

    if attempt("page token", page_token):
        print(f"  {'page token':10} obtained (not shown)")
    accounts = attempt("page tasks", lambda: get("me/accounts", fields="id,tasks"))
    if accounts is not None:
        tasks = next((a.get("tasks", []) for a in accounts.get("data", []) if a.get("id") == PAGE_ID), None)
        if tasks is None:
            print(f"  {'page tasks':10} Page not listed under me/accounts (assignment may be via the business)")
        elif "CREATE_CONTENT" not in tasks:
            problems.append(f"system user's Page tasks lack CREATE_CONTENT: {tasks}")
            print(f"  {'page tasks':10} {', '.join(tasks)}  (CREATE_CONTENT MISSING)")
        else:
            print(f"  {'page tasks':10} {', '.join(tasks)}")

    ig = attempt("instagram", lambda: get(INSTAGRAM_ID, fields="username,name,website,media_count"))
    if ig:
        print(f"  {'instagram':10} {ig.get('name')} (@{ig.get('username')}), {ig.get('media_count')} media, "
              f"bio link {ig.get('website') or 'NONE'}")
        if not ig.get("website"):
            problems.append("the Instagram bio has no website, so 'link in bio' points nowhere")
    quota = attempt("ig quota", lambda: get(f"{INSTAGRAM_ID}/content_publishing_limit", fields="config,quota_usage"))
    if quota:
        row = (quota.get("data") or [{}])[0]
        total = (row.get("config") or {}).get("quota_total", "?")
        print(f"  {'ig quota':10} {row.get('quota_usage', '?')} of {total} API posts used in the last 24h")

    if problems:
        print("\nPROBLEMS")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    print("\nall checks passed: the token can read and publish to the Page and to Instagram")


def _short(text: str | None, width: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[:width - 3] + "..."


def cmd_recent(args) -> None:
    print(f"Facebook Page {PAGE_ID}")
    rows = get(f"{PAGE_ID}/posts", page_token(), fields="id,created_time,message,permalink_url",
               limit=args.limit).get("data", [])
    for row in rows:
        print(f"  {row.get('created_time', '')[:16].replace('T', ' ')}  {row.get('permalink_url')}")
        print(f"  {'':16}  {_short(row.get('message')) or '(no text)'}")
    if not rows:
        print("  no posts")
    print(f"\nInstagram {INSTAGRAM_ID}")
    rows = get(f"{INSTAGRAM_ID}/media", fields="id,timestamp,media_type,caption,permalink",
               limit=args.limit).get("data", [])
    for row in rows:
        print(f"  {row.get('timestamp', '')[:16].replace('T', ' ')}  {row.get('media_type', ''):14}  {row.get('permalink')}")
        print(f"  {'':16}  {_short(row.get('caption')) or '(no caption)'}")
    if not rows:
        print("  no media")


def prepare(args) -> tuple[dict, dict, list[str]]:
    """Fetch the event, build captions, validate. Returns (event, plan by platform, blocking errors)."""
    event = fetch_event(args.slug, public_api_key(args.api_key))
    image = args.image or event.get("imageUrl")
    errors, warnings, summary = check_image(image)

    status = event.get("status")
    if status in ("past", "cancelled"):
        errors.append(f"the event is {status}; refusing to promote it")
    elif status in ("sold-out", "postponed"):
        warnings.append(f"the event is {status}")

    for lang in caption_languages(event, args.lang):
        broken = check_link(event_url(event, lang))
        if broken:
            errors.append(broken)

    plan = {}
    for platform in ("facebook", "instagram"):
        caption = build_caption(event, args.lang, platform)
        errors.extend(caption_problems(caption, platform))
        plan[platform] = caption

    print(f"event     {event['name']} ({event['slug']}), {event['date']}, language {event.get('language')}, "
          f"status {status}, tags {', '.join(event.get('tags') or []) or 'none'}")
    print(f"image     {image or 'NONE'}")
    print(f"          {summary}" + ("  (from --image)" if args.image else ""))
    for lang in caption_languages(event, args.lang):
        print(f"link {lang}   {event_url(event, lang)}")
    for platform, caption in plan.items():
        endpoint = f"POST /{PAGE_ID}/photos  url + caption" if platform == "facebook" else (
            f"POST /{INSTAGRAM_ID}/media  image_url + caption, then /media_publish")
        print(f"\n===== {platform.upper()}  ({endpoint}, {len(caption)} characters) =====")
        print(caption)
        print("=" * 40)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"BLOCKED: {error}")
    return {**event, "_image": image}, plan, errors


def cmd_draft(args) -> None:
    _, _, errors = prepare(args)
    if errors:
        sys.exit("\ndraft only; this event cannot be posted until the BLOCKED items above are fixed")
    print("\ndraft only, nothing was posted. Publish with: "
          f"scripts/meta-social.py post {args.slug} --to both --lang {args.lang}"
          + (f" --image {args.image}" if args.image else "") + " --confirm")


def publish_facebook(image: str, caption: str) -> None:
    pt = page_token()
    result = post(f"{PAGE_ID}/photos", pt, url=image, caption=caption, published="true")
    post_id = result.get("post_id") or result.get("id")
    link = get(post_id, pt, fields="permalink_url").get("permalink_url") if post_id else None
    print(f"facebook  published: photo {result.get('id')}, post {result.get('post_id')}, {link}")


def publish_instagram(image: str, caption: str, wait_seconds: int = 120) -> None:
    container = post(f"{INSTAGRAM_ID}/media", image_url=image, caption=caption).get("id")
    if not container:
        raise GraphError("Instagram did not return a media container id")
    print(f"instagram container {container} created, waiting for it to process")
    deadline = time.monotonic() + wait_seconds
    while True:
        state = get(container, fields="status_code,status")
        code = state.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise GraphError(f"Instagram container {container} is {code}: {state.get('status')}")
        if time.monotonic() > deadline:
            raise GraphError(f"Instagram container {container} still {code} after {wait_seconds}s; nothing published")
        time.sleep(3)
    media_id = post(f"{INSTAGRAM_ID}/media_publish", creation_id=container).get("id")
    link = get(media_id, fields="permalink").get("permalink") if media_id else None
    print(f"instagram published: media {media_id}, {link}")


def cmd_post(args) -> None:
    event, plan, errors = prepare(args)
    if not args.confirm:
        blocked = " It also has BLOCKED items that --confirm will not override." if errors else ""
        print(f"\nNOT POSTED: this was a draft. Re-run with --confirm to publish to {args.to}.{blocked}",
              file=sys.stderr)
        sys.exit(2)
    if errors:
        sys.exit("\nnot posted: fix the BLOCKED items above first")
    targets = ["facebook", "instagram"] if args.to == "both" else [args.to]
    print()
    done = []
    for platform in targets:
        try:
            if platform == "facebook":
                publish_facebook(event["_image"], plan["facebook"])
            else:
                publish_instagram(event["_image"], plan["instagram"])
            done.append(platform)
        except GraphError as exc:
            already = f" ({', '.join(done)} WAS already published, do not re-run --to both)" if done else ""
            sys.exit(f"{platform} FAILED: {exc}{already}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="check the token sees the Page and IG and can publish").set_defaults(func=cmd_whoami)

    recent = sub.add_parser("recent", help="latest Page posts and IG media")
    recent.add_argument("--limit", type=int, default=5)
    recent.set_defaults(func=cmd_recent)

    for name, handler, helptext in (("draft", cmd_draft, "print and validate what would be posted"),
                                    ("post", cmd_post, "publish (requires --confirm)")):
        command = sub.add_parser(name, help=helptext)
        command.add_argument("slug", help="event slug from the public API")
        command.add_argument("--lang", choices=("en", "es", "both"), default="both")
        command.add_argument("--image", help="https URL of an image to use instead of the event's own")
        command.add_argument("--api-key", help="public API key (default: $IGUANA_PUBLIC_API_KEY, then ssh)")
        if name == "post":
            command.add_argument("--to", choices=("facebook", "instagram", "both"), required=True)
            command.add_argument("--confirm", action="store_true", help="actually publish")
        command.set_defaults(func=handler)

    args = parser.parse_args()
    try:
        args.func(args)
    except GraphError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
