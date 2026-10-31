"""Profil koneksi untuk /connect: deteksi gaya API per endpoint (OpenAI-compatible vs Anthropic native) supaya
daftar model bisa diambil lewat HTTP dari endpoint APA PUN — Inttelix, OpenRouter, Anthropic, atau proxy custom.

Chat tetap memakai bentuk OpenAI-compatible (cx/api.py): cocok untuk Inttelix, OpenRouter, dan kebanyakan proxy
(termasuk endpoint cadangan GPT 5.6 Sol — path-nya sendiri berakhiran /chat/completions). Endpoint Anthropic asli
hanya didukung untuk DAFTAR MODEL di sini; chat native Anthropic (bentuk pesan berbeda) belum diimplementasikan.
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

ANTHROPIC_VERSION = "2023-06-01"

KNOWN = {
    "inttelix.vercel.app": ("Inttelix", "openai"),
    "openrouter.ai": ("OpenRouter", "openai"),
    "api.anthropic.com": ("Anthropic", "anthropic"),
    "api.manus.im": ("Manus", "openai"),
    "api.openai.com": ("OpenAI", "openai"),
    "api.groq.com": ("Groq", "openai"),
    "api.together.xyz": ("Together AI", "openai"),
    "api.deepseek.com": ("DeepSeek", "openai"),
}
QUICK_PICKS = [("inttelix", "https://inttelix.vercel.app/api/v1", "bawaan CodinX"),
               ("manus", "https://api.manus.im/api/llm-proxy/v1", "Manus Proxy · katalog model lokal"),
               ("openrouter", "https://openrouter.ai/api/v1", "ratusan model, satu key"),
               ("anthropic", "https://api.anthropic.com", "API resmi Anthropic (hanya daftar model)"),
               ("custom", "", "endpoint lain / proxy milikmu sendiri")]

# Katalog lokal Manus: ID dipakai hanya untuk request; nama adalah label di UI.
# Endpoint Manus tidak menyediakan /models yang perlu dipanggil saat /connect.
MANUS_MODELS = [
    {"id": "gpt-5", "name": "GPT-5", "role": "PRO", "trial": 0, "price": ""},
    {"id": "gpt-5.5", "name": "GPT-5.5", "role": "MAX", "trial": 0, "price": ""},
    {"id": "gpt-5-mini", "name": "GPT-5 Mini", "role": "FREE", "trial": 0, "price": ""},
    {"id": "gpt-5-nano", "name": "GPT-5 Nano", "role": "FREE", "trial": 0, "price": ""},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "role": "FREE", "trial": 0, "price": ""},
    {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "role": "FREE", "trial": 0, "price": ""},
    {"id": "claude-opus-4-7", "name": "/.GPT 5.6 Sol", "role": "PRO", "trial": 0, "price": "", "display_alias": True},
    {"id": "claude-sonnet-4-6", "name": "/.GPT 5.6 TERRA", "role": "FREE", "trial": 0, "price": "", "display_alias": True},
    {"id": "claude-haiku-4-5", "name": "/.GPT 5.6 LUNA", "role": "FREE", "trial": 0, "price": "", "display_alias": True},
    {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro", "role": "PRO", "trial": 0, "price": ""},
    {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "role": "FREE", "trial": 0, "price": ""},
    {"id": "gemini-2.5-flash", "name": "/. Gemini 3.5 Flash Lite", "role": "FREE", "trial": 0, "price": "", "display_alias": True},
]


def is_manus_endpoint(base_url):
    parsed = urllib.parse.urlparse(base_url or "")
    return parsed.hostname == "api.manus.im" and "/api/llm-proxy" in (parsed.path or "")


def manus_model_specs():
    return [dict(m) for m in MANUS_MODELS]


class ConnectError(Exception):
    def __init__(self, msg, attempts=None):
        super().__init__(msg)
        self.attempts = attempts or []


def label_for(base_url):
    host = urllib.parse.urlparse(base_url).netloc.lower()
    for dom, (name, _) in KNOWN.items():
        if dom in host:
            return name
    return host or "custom"


def style_for(base_url):
    host = urllib.parse.urlparse(base_url).netloc.lower()
    for dom, (_, style) in KNOWN.items():
        if dom in host:
            return style
    return "openai"


def display_model_name(base_url, model_id):
    if is_manus_endpoint(base_url):
        for item in MANUS_MODELS:
            if item["id"] == model_id:
                return item["name"]
    return model_id


def _ctx(insecure):
    if not insecure:
        return None
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def _get(url, headers, timeout, insecure):
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx(insecure)) as r:
        return json.loads(r.read().decode())


def _ids_from_openai(obj):
    items = obj.get("data", obj) if isinstance(obj, dict) else obj
    return sorted({(m.get("id") if isinstance(m, dict) else str(m)) for m in items if m})


def _ids_from_anthropic(obj):
    return sorted({m["id"] for m in obj.get("data", []) if m.get("id")})


def _try_openai(base_url, key, timeout, insecure):
    url = base_url.rstrip("/")
    if not url.endswith(("/models",)):
        url += "/models"
    obj = _get(url, {"Authorization": "Bearer " + key, "User-Agent": "CodinX/1.4"}, timeout, insecure)
    return _ids_from_openai(obj)


def _try_anthropic(base_url, key, timeout, insecure):
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    obj = _get(root + "/v1/models", {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "User-Agent": "CodinX/1.4"}, timeout, insecure)
    return _ids_from_anthropic(obj)


def list_models(base_url, key, style=None, timeout=120, insecure=False):
    """-> (ids, style_used). Manus memakai katalog lokal dan tidak memanggil endpoint /models."""
    if is_manus_endpoint(base_url):
        return [m["id"] for m in MANUS_MODELS], "openai"
    order = [style or style_for(base_url)]
    order += [s for s in ("openai", "anthropic") if s not in order]
    attempts = []
    for s in order:
        try:
            fn = _try_openai if s == "openai" else _try_anthropic
            ids = fn(base_url, key, timeout, insecure)
            if ids:
                return ids, s
            attempts.append(f"{s}: 0 model dikembalikan")
        except urllib.error.HTTPError as e:
            attempts.append(f"{s}: HTTP {e.code}")
        except urllib.error.URLError as e:
            attempts.append(f"{s}: {getattr(e, 'reason', e)}")
        except (ValueError, KeyError, TypeError) as e:
            attempts.append(f"{s}: respons tak terduga ({type(e).__name__})")
    raise ConnectError("Gagal mengambil daftar model dari semua gaya API yang dicoba.", attempts)
