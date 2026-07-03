import re
import asyncio
import json
from urllib.parse import urljoin, urlparse

from curl_cffi import requests as cffi_requests

# ── Universal Quality Spec Table ────────────────────────────────────────────

QUALITY_SPECS = [
    {
        'type':    'res_p',
        'pattern': re.compile(r'(\d{3,4})p', re.IGNORECASE),
        'extract': lambda m: int(m.group(1)),
        'ladder':  [144, 240, 360, 480, 720, 1080, 1440, 2160, 4320],
        'format':  lambda v: f'{v}p',
    },
    {
        'type':    'res_wh',
        'pattern': re.compile(r'(\d{3,5})x(\d{3,4})', re.IGNORECASE),
        'extract': lambda m: int(m.group(2)),           # rank by height
        'ladder':  [144, 240, 360, 480, 720, 1080, 1440, 2160],
        'format':  lambda v: {                          # height → WxH pair
            144:'256x144', 240:'426x240',  360:'640x360',
            480:'854x480', 720:'1280x720', 1080:'1920x1080',
            1440:'2560x1440', 2160:'3840x2160'
        }[v] if v in [144, 240, 360, 480, 720, 1080, 1440, 2160] else f'{v}x{v}',
    },
    {
        'type':    'bitrate_k',
        'pattern': re.compile(r'(\d{3,5})[kK](?:bps)?\b'),
        'extract': lambda m: int(m.group(1)),
        'ladder':  [300, 500, 800, 1200, 2000, 3000, 5000, 8000, 12000],
        'format':  lambda v: f'{v}k',
    },
    {
        'type':    'bitrate_raw',
        'pattern': re.compile(r'(?<=[/_\-=,])(\d{6,8})(?=[/_\-=,\.?&])'),
        'extract': lambda m: int(m.group(1)),
        'ladder':  [300_000, 500_000, 1_000_000, 2_000_000,
                    3_000_000, 5_000_000, 8_000_000, 12_000_000],
        'format':  lambda v: str(v),
    },
    {
        'type':    'label',
        'pattern': re.compile(r'(?<=[/_\-=,])(uhd|fhd|hd|sd)(?=[/_\-=,\.])', re.IGNORECASE),
        'extract': lambda m: ['sd', 'hd', 'fhd', 'uhd'].index(m.group(1).lower()),
        'ladder':  [0, 1, 2, 3],
        'format':  lambda v: ['sd', 'hd', 'fhd', 'uhd'][v],
    },
]

def detect_quality_token(url: str):
    """ Find the first quality indicator in any URL. No site knowledge needed. """
    for spec in QUALITY_SPECS:
        m = spec['pattern'].search(url)
        if m:
            return spec, m
    return None, None

def generate_upgrade_candidates(url: str, spec: dict, match) -> list[str]:
    """ Swap the detected token with every higher value in its ladder. """
    current = spec['extract'](match)
    candidates = []
    for val in reversed(spec['ladder']):   # highest quality first
        if val <= current:
            continue
        new_token = spec['format'](val)
        candidate = url[:match.start()] + new_token + url[match.end():]
        candidates.append(candidate)
    return candidates

# ── Sibling URL Differ ──────────────────────────────────────────────────────

def _tokenize(url: str) -> list[str]:
    """ Split URL into tokens + delimiters so diffs are token-level. """
    return re.split(r'([/_\-=.:,?&@!])', url)

def find_quality_axis_from_siblings(urls: list[str]) -> tuple[str, list[str]] | None:
    """ Compares all captured URLs structurally. """
    if len(urls) < 2:
        return None

    tokenized = [_tokenize(u) for u in urls]
    ref_len   = len(tokenized[0])

    if not all(len(t) == ref_len for t in tokenized):
        return None

    diff_positions = [
        i for i in range(ref_len)
        if len({t[i] for t in tokenized}) > 1
    ]

    if len(diff_positions) != 1:
        return None

    pos      = diff_positions[0]
    variants = list({t[pos] for t in tokenized})
    template = ''.join(
        ('{Q}' if i == pos else tok)
        for i, tok in enumerate(tokenized[0])
    )
    return template, variants

def extrapolate_from_siblings(template: str, known_variants: list[str]) -> list[str]:
    """ Generate URLs for ALL higher quality values using the appropriate spec. """
    for spec in QUALITY_SPECS:
        matches = [spec['pattern'].search(v) for v in known_variants]
        if not all(matches):
            continue

        max_known = max(spec['extract'](m) for m in matches)

        return [
            template.replace('{Q}', spec['format'](val))
            for val in reversed(spec['ladder'])
            if val > max_known
        ]

    return []

# ── Helper Functions ────────────────────────────────────────────────────────

def _fetch_sync(url: str, referer: str, cookies: dict = None) -> str | None:
    """
    Fetch a URL while impersonating a real Chrome browser (TLS fingerprint)
    and forwarding the harvested browser session cookies.
    Bypasses Cloudflare and CDN token validation that blocks standard clients.
    """
    try:
        response = cffi_requests.get(
            url,
            headers={
                'Referer': referer,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
            },
            cookies=cookies or {},
            timeout=10,
            impersonate="chrome",
            allow_redirects=True,
        )
        if response.status_code == 200:
            return response.text
    except Exception:
        return None
    return None

async def _fetch(url: str, referer: str, cookies: dict = None) -> str | None:
    return await asyncio.to_thread(_fetch_sync, url, referer, cookies)

def _is_master(content: str) -> bool:
    return '#EXT-X-STREAM-INF' in content
    
def _extract_url_from_json(content: str) -> str | None:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict) and "url" in data["data"]:
                return data["data"]["url"]
            if "url" in data:
                return data["url"]
        def search(obj):
            if isinstance(obj, str) and '.m3u8' in obj:
                return obj
            if isinstance(obj, dict):
                for k, v in obj.items():
                    res = search(v)
                    if res: return res
            if isinstance(obj, list):
                for item in obj:
                    res = search(item)
                    if res: return res
            return None
        return search(data)
    except:
        return None

def _best_variant_from_master(content: str, master_url: str) -> str:
    # Because yt-dlp parses the master playlist correctly and stitches audio/video,
    # returning the master URL directly is the safest and best approach!
    return master_url

async def _probe_master(url: str, referer: str, cookies: dict = None) -> tuple[str, str] | None:
    """ Try common master names at the same level as the playlist. """
    parts = url.split('/')
    original_last = parts[-1]
    
    for candidate in ['master.m3u8', 'index.m3u8', 'playlist.m3u8']:
        if original_last == candidate:
            continue
            
        parts[-1] = candidate
        probe_url = '/'.join(parts)
        content = await _fetch(probe_url, referer, cookies)
        if content and _is_master(content):
            print(f"  [+] Probed master successfully: {probe_url}")
            return probe_url, content
            
    return None

# ── Unified HLS Maximizer ───────────────────────────────────────────────────

async def maximize_hls(m3u8_urls: list[str], referer: str, cookies: list = None) -> str | None:
    if not m3u8_urls:
        return None
    
    # Convert Playwright cookie list to a simple dict for curl_cffi
    cookie_jar = {c['name']: c['value'] for c in (cookies or [])}
    if cookie_jar:
        print(f"  [QM] Using {len(cookie_jar)} session cookies for manifest fetches.")
        
    m3u8_urls = list(set(m3u8_urls))
    
    print(f"\n[QM] Analyzing {len(m3u8_urls)} m3u8 URL(s)...")

    # ── Step 1: Check if any captured URL IS already a master ────────────────
    extracted_urls = []
    for url in m3u8_urls:
        content = await _fetch(url, referer, cookie_jar)
        if content:
            json_url = _extract_url_from_json(content)
            if json_url:
                print(f"  [+] Extracted M3U8 from JSON -> {json_url}")
                url = json_url
                content = await _fetch(url, referer, cookie_jar)
            if content and _is_master(content):
                best = _best_variant_from_master(content, url)
                print(f"  [+] Direct master found -> best variant: {best}")
                return best or url
        extracted_urls.append(url)
                
    m3u8_urls = extracted_urls

    # ── Step 2: Sibling diff (works for ANY CDN, no pattern knowledge needed)
    axis = find_quality_axis_from_siblings(m3u8_urls)
    if axis:
        template, known = axis
        print(f"  [+] Quality axis found via URL diff. Known: {known}")
        print(f"  [~] Template: {template}")
        candidates = extrapolate_from_siblings(template, known)
        for c in candidates:
            content = await _fetch(c, referer, cookie_jar)
            if content:
                if _is_master(content):
                    best = _best_variant_from_master(content, c)
                    print(f"  [✓] Extrapolated master!")
                    return best or c
                print(f"  [✓] Extrapolated variant: {c}")
                return c

    # ── Step 3: Generic token mutation on best single URL ────────────────────
    def score_url(u):
        spec, match = detect_quality_token(u)
        if spec and match:
            return spec['extract'](match)
        return 0
        
    best_url = max(m3u8_urls, key=score_url)
    spec, match = detect_quality_token(best_url)

    if spec and match:
        print(f"  [~] Token detected: type={spec['type']}  "
              f"value={spec['extract'](match)}  → generating upgrades...")
        for candidate in generate_upgrade_candidates(best_url, spec, match):
            content = await _fetch(candidate, referer, cookie_jar)
            if content:
                print(f"  [✓] Mutated URL works: {candidate}")
                return candidate

    # ── Step 4: Master manifest probe at parent path ─────────────────────────
    result = await _probe_master(best_url, referer, cookie_jar)
    if result:
        master_url, content = result
        best = _best_variant_from_master(content, master_url)
        return best or master_url

    print(f"  [!] All strategies exhausted. Returning best available.")
    return best_url
