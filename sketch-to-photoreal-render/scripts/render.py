#!/usr/bin/env python3
"""render.py - sketch / plan / SketchUp export -> photoreal architectural render, 1K first.

Gemini (gemini-3-pro-image, legacy generateContent) makes the pixels. This CLI wraps the
local app's pipeline around one call per pass: the source is edge-extended to the nearest
aspect ratio the model offers, rendered at that ratio, the source's own rectangle is cropped
back out, and every pass ships a before/after comparison sheet.

Standing policy (quoted, not paraphrased):

    Final rule: Always render edits in 1K first, then enhance to 4K only after explicit
    confirmation.

    in all the future render, after every render i want comparison sheet to cross verify.
    update everywhere.

Commands
    check [--online]          environment, sheet font, key source, model; --online makes the
                              FREE models.get metadata call (never billed)
    render <input> [...]      first pass from a sketch, plan, export or PDF (page 1), at 1K
    revise <render> --notes   one change on the current render, at 1K
    patch <render> --box x0,y0,x1,y1 --notes   local edit of one region, at 1K
    upscale <render> --confirmed               4K re-render of ONE approved image
    sheet <render>            rebuild that pass's comparison sheet (local, free)
    status [DIR]              jobs, passes, files, warnings, attempts and list-price cost

Spend gate: render / revise / patch without --dry-run, --prompt-only or --spend-ok print an
estimate and exit 3 without reading the API key. upscale without --confirmed exits 2 (and
prints what the 4K pass would cost if the user approves that file).

Exit codes: 0 done; 1 error; 2 refused (policy gate or bad arguments); 3 spend gate
(estimate printed, nothing sent); 4 delivered but needs attention (re-framed, lineage
warning, wrong size tier, or the comparison sheet is missing).

Nothing is ever written inside the skill folder: pass --out for the bundled test sketch.

Standard library + Pillow (+ PyMuPDF for PDF input). The two vendored modules,
_render_common.py and comparison_sheet.py, are byte-identical copies of the originals; every
adaptation lives in this file.
"""
import argparse, atexit, glob, http.client, json, math, os, re, shutil, sys, tempfile, time
import unicodedata, urllib.error, urllib.parse, urllib.request
from datetime import datetime

# The installed skill folder may be synced, zipped or uploaded: never leave __pycache__ in it.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))          # <skill>/scripts
SKILL_DIR = os.path.dirname(HERE)                           # <skill>

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ===================================================== sheet font (before the sheet import)
# comparison_sheet.py reads COMPARISON_FONT_DIR when it is imported and otherwise looks only
# in C:\Windows\Fonts. On macOS or Linux, find Century Gothic (or URW Gothic, the closest
# geometric sans) and hand it over through that variable - without editing the vendored file
# and without bundling the font, which is licensed.
WIN_GOTHIC = r"C:\Windows\Fonts\GOTHIC.TTF"


def font_candidates():
    """(label, regular, bold) places Century Gothic or URW Gothic is commonly installed."""
    home = os.path.expanduser("~")
    cands = []
    la = os.environ.get("LOCALAPPDATA", "")
    if la:
        d = os.path.join(la, "Microsoft", "Windows", "Fonts")
        cands.append(("Century Gothic (per-user Windows fonts)",
                      os.path.join(d, "GOTHIC.TTF"), os.path.join(d, "GOTHICB.TTF")))
    mac = ["/Library/Fonts", "/Library/Fonts/Microsoft", os.path.join(home, "Library", "Fonts")]
    mac += ["/Applications/Microsoft %s.app/Contents/Resources/DFonts" % app
            for app in ("Word", "PowerPoint", "Excel", "Outlook")]
    for d in mac:
        cands.append(("Century Gothic (%s)" % d, os.path.join(d, "Century Gothic.ttf"),
                      os.path.join(d, "Century Gothic Bold.ttf")))
        cands.append(("Century Gothic (%s)" % d, os.path.join(d, "GOTHIC.TTF"),
                      os.path.join(d, "GOTHICB.TTF")))
    for d in ("/usr/share/fonts/opentype/urw-base35", "/usr/share/fonts/urw-base35",
              "/usr/share/fonts/OTF", "/usr/local/share/fonts",
              os.path.join(home, ".local", "share", "fonts"), os.path.join(home, ".fonts")):
        cands.append(("Century Gothic (%s)" % d, os.path.join(d, "GOTHIC.TTF"),
                      os.path.join(d, "GOTHICB.TTF")))
        cands.append(("URW Gothic (%s) - the closest geometric sans, substituted for "
                      "Century Gothic" % d, os.path.join(d, "URWGothic-Book.otf"),
                      os.path.join(d, "URWGothic-Demi.otf")))
    return cands


def setup_sheet_fonts(win_regular=WIN_GOTHIC, candidates=None):
    """Make Century Gothic (or the nearest substitute) visible to comparison_sheet.py.
    Returns (status line, substituted?)."""
    given = os.environ.get("COMPARISON_FONT_DIR", "").strip()
    if given:
        ok = os.path.isfile(os.path.join(given, "GOTHIC.TTF"))
        return ("COMPARISON_FONT_DIR=%s (%s)" % (given, "GOTHIC.TTF found" if ok else
                "GOTHIC.TTF missing there - sheets fall back to Pillow's default font"), False)
    if os.path.isfile(win_regular):
        return ("Century Gothic (%s)" % os.path.dirname(win_regular), False)
    for label, reg, bold in (font_candidates() if candidates is None else candidates):
        if not os.path.isfile(reg):
            continue
        tmp = tempfile.mkdtemp(prefix="render-skill-fonts-")
        atexit.register(shutil.rmtree, tmp, True)
        shutil.copyfile(reg, os.path.join(tmp, "GOTHIC.TTF"))
        shutil.copyfile(bold if os.path.isfile(bold) else reg, os.path.join(tmp, "GOTHICB.TTF"))
        os.environ["COMPARISON_FONT_DIR"] = tmp
        return ("%s, copied to %s as GOTHIC.TTF / GOTHICB.TTF" % (label, tmp), True)
    return ("NOT FOUND - sheets use Pillow's default font. Install Century Gothic (or on "
            "Linux: apt install fonts-urw-base35) for correctly styled sheets", True)


FONT_STATUS, FONT_SUBSTITUTED = setup_sheet_fonts()

REQUIREMENTS = os.path.join(HERE, "requirements.txt")
sys.path.insert(0, HERE)
import _render_common as rc                         # noqa: E402  (vendored, byte-identical)
import comparison_sheet as cs                       # noqa: E402  (vendored, byte-identical)
try:
    from PIL import Image, ImageOps                 # noqa: E402
except ImportError:
    sys.exit("!! Pillow is not installed for this Python (%s).\n   Install it, then run "
             "'render.py check' again:\n     \"%s\" -m pip install -r \"%s\""
             % (sys.executable, sys.executable, REQUIREMENTS))

if FONT_SUBSTITUTED:
    print("sheet font: " + FONT_STATUS, flush=True)


# ================================================================== constants
# Lifted from the local app (app.py) unless marked otherwise.
DRAFT_SIZE = os.environ.get("IMAGE_SIZE", rc.DEFAULT_IMAGE_SIZE)
MAX_ATTEMPTS = 3                 # skill rule: a retry count is never raised to rescue a prompt


def env_attempts():
    """ATTEMPTS from the environment (default 2). Returns (n, note); a value that is not a
    whole number falls back to 2 with a note instead of crashing every command."""
    raw = os.environ.get("ATTEMPTS", "").strip()
    if not raw:
        return 2, None
    try:
        return max(1, int(raw)), None
    except ValueError:
        return 2, "ATTEMPTS=%r is not a whole number - using the default of 2" % raw


ATTEMPTS, ATTEMPTS_NOTE = env_attempts()   # every attempt is billed
FEED_MAX_EDGE = 2400            # the model outputs ~1K; feeding more is wasted payload
USD_PER_1K_IMAGE = 0.134        # list price, from CLAUDE.md
INR_PER_USD = rc.INR_PER_4K_IMAGE / rc.USD_PER_4K_IMAGE
MODEL = os.environ.get("MODEL", rc.MODEL)
# The vendored generate() builds its URL from the model id and the key. A space or control
# character in MODEL (e.g. a stray trailing space in $env:MODEL) would make urllib raise an
# error whose text is that URL, key included - so a malformed id is refused before any call.
MODEL_OK = bool(re.fullmatch(r"[A-Za-z0-9._-]{1,100}", MODEL))
MODEL_PROBLEM = ("the MODEL environment variable %r is not a valid model id (letters, digits, "
                 "'.', '_' and '-' only - a stray space or quote?). Fix or remove it; the "
                 "default is %s." % (MODEL, rc.MODEL))
NOTES_MAX = 4000
# Local files, not web uploads: images up to 100 MP are accepted (the local app caps uploads at 40 MP;
# the 9999 px SketchUp exports in this tree are 43-51 MP). The PDF dpi formula keeps 40 MP.
PIXEL_CAP = 100_000_000
PDF_PIXEL_CAP = 40_000_000
Image.MAX_IMAGE_PIXELS = PIXEL_CAP
GOOGLE_API_BASE = "https://generativelanguage.googleapis.com"

IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}
RATIOS = {"1:1": 1.0, "2:3": 2 / 3, "3:2": 1.5, "3:4": 0.75, "4:3": 4 / 3, "4:5": 0.8,
          "5:4": 1.25, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9}
DOS_DEVICES = ({"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)}
               | {"LPT%d" % i for i in range(1, 10)})

CANVAS_NOTE = (
    "\n\nCANVAS: the attached image has been extended with a thin {where} band of smeared, "
    "stretched edge pixels so it fits the output format. That band is filler, not design. "
    "Keep the whole scene exactly where it sits in the canvas at exactly its size - do not "
    "re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, "
    "ground) into it."
)

REVISE_HEADER = (
    "EDIT THIS PHOTOGRAPH. Its framing is already correct; keep it high-end DSLR "
    "architectural photography. Keep the camera, framing, every wall, opening, slab, "
    "roof, pool, deck, plant position, the light and the colour grade identical, and "
    "add or remove nothing, EXCEPT for these changes:"
)

# The 4K brief deliberately omits FIDELITY_PROMPT's materials paragraph: it names
# example finishes (terracotta tiles) and on a job whose approved scheme differs it
# quietly undoes the approval during the resolution pass (see upscale_to_4k.py
# --prompt-file). The approved image itself is the materials reference here.
UPSCALE_LOOK = (
    "OUTPUT LOOK: high-end DSLR architectural photography - true perspective, physically "
    "correct exposure, sharp focus, natural lighting, accurate white balance, faint natural "
    "sensor grain. No CGI / 3D-render look, no illustration, no text, no logos, no people."
)
LOCKED_FINISHES = (
    "LOCKED FINISHES: every material, colour, plant, texture and light in the attached "
    "approved image is final. Reproduce them exactly at higher resolution. Do not substitute "
    "any finish for another, however typical the alternative may be."
)

# From project 18/render_p18_1k.py lines 54-60.
# The shared fidelity brief names terracotta tiles as its example roof finish. This villa has
# flat membrane roofs, and with that line in the prompt view 04's first pass came back with
# red tiled hip roofs (21 Sep 2026). Drop the example here only; the shared helper is untouched.
TERRACOTTA = "terracotta roof tiles with true clay colour variation and weathering; "
if TERRACOTTA not in rc.FIDELITY_PROMPT:
    sys.exit("shared FIDELITY_PROMPT changed - re-check the terracotta override in %s" % __file__)
FIDELITY = rc.FIDELITY_PROMPT.replace(TERRACOTTA, "")

# From project 18/patch_p18_1k.py lines 39-45 (project 19's patch method).
FEATHER = 36

HEADER = ("EDIT THIS PHOTOGRAPH. It is a close-up crop of a larger architectural photograph and will be "
          "pasted back into it, so keep the camera, framing, scale, light and colour grade identical. The "
          "change below is required and must be clearly visible; everything else in the crop stays exactly "
          "as it is. Make this change:")
TAIL = "\n\nOutput ONE photograph with exactly the same framing as this crop."

REMINDER = (
    "REFUSING to run: 4K rendering needs explicit confirmation.\n"
    "\n"
    "Standing policy, quoted:\n"
    "  \"Final rule: Always render edits in 1K first, then enhance to 4K only after explicit\n"
    "  confirmation.\"\n"
    "4K is ONLY for one image the user has already seen on its comparison sheet and approved by\n"
    "name - never for drafts, edits or revisions, and never for a whole set at once. \"Looks good\"\n"
    "on a set, or \"make it sharper\", is not approval: ask which single image.\n"
    "\n"
    "If the user has approved this exact image, re-run with --confirmed:\n"
    "  python render.py upscale --confirmed <approved image>"
)

EXIT_OK, EXIT_ERROR, EXIT_REFUSED, EXIT_SPEND_GATE, EXIT_ATTENTION = 0, 1, 2, 3, 4


class Refused(Exception):
    """A policy gate or bad argument: exit 2, nothing spent."""


class Failed(Exception):
    """An error the user must fix: exit 1."""


# =============================================================== small utils
def now():
    return datetime.now().isoformat(timespec="seconds")


def rel(out, path):
    """Path stored in job files: relative to the output folder (or its parent, e.g. a sibling
    '02 Input'), forward slashes; anything further away is stored absolute."""
    try:
        r = os.path.relpath(path, out).replace("\\", "/")
    except ValueError:                       # another drive on Windows
        r = None
    if r is None or r.startswith("../../") or r == "..":
        return os.path.abspath(path).replace("\\", "/")
    return r


def absp(out, relpath):
    return os.path.normpath(os.path.join(out, relpath))


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def safe_name(name, fallback="sketch", strip_ext=False):
    """A view name that is safe as a Windows file stem.

    strip_ext=True is for an upload's file name; a typed name only loses a trailing
    image/pdf extension, so "Villa No. 3" stays "Villa No. 3". A slash in a typed name is a
    separator, not a folder ("Block A/B" -> "Block A - B"), and accented letters are
    transliterated ("Ñandú" -> "Nandu") instead of being dropped.
    """
    s = str(name or "")
    if not strip_ext:
        s = re.sub(r"\s*[\\/]+\s*", " - ", s)
    base = os.path.basename(s)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    if strip_ext:
        base = os.path.splitext(base)[0]
    else:
        base = re.sub(r"\.(png|jpe?g|webp|pdf)$", "", base, flags=re.I)
    base = re.sub(r"[^A-Za-z0-9 _()&.-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip(" ._-")[:60].strip(" ._-")
    if not base:
        base = fallback
    if base.split(".")[0].strip().upper() in DOS_DEVICES:      # CON.png is a device
        base = "_" + base
    return base


def free_stem(out, stem):
    """First of stem, 'stem (2)', 'stem (3)'... with no existing output, raw or sheet, so
    a pass never writes over what an earlier pass delivered."""
    work = os.path.join(out, "_work")
    cand, i = stem, 1
    while (os.path.exists(os.path.join(out, cand + ".png"))
           or glob.glob(os.path.join(work, glob.escape(cand) + "_raw.*"))
           or os.path.exists(os.path.join(work, cand + "_padded.jpg"))
           or os.path.exists(os.path.join(out, "_Before After - %s.jpg" % cand))):
        i += 1
        cand = "%s (%d)" % (stem, i)
    return cand


def next_rev_stem(out, current_stem, from_size=None, to_size=None):
    """'Villa_1K' -> 'Villa_1K_rev02'; 'Villa_1K_rev02' -> 'Villa_1K_rev03'. Numbered from
    the file actually being revised, so a failed revision leaves no gap. The tier in the name
    is the tier the new file is rendered at: revising 'Villa_2K' at the 1K draft tier gives
    'Villa_1K_rev02'."""
    m = re.match(r"^(.*)_rev(\d+)$", current_stem)
    base, n = (m.group(1), int(m.group(2))) if m else (current_stem, 1)
    if from_size and to_size and from_size != to_size:
        base = re.sub(r"_%s(?=( \(\d+\))?$)" % re.escape(from_size), "_" + to_size, base)
    return free_stem(out, "%s_rev%02d" % (base, n + 1))


def price(size):
    return rc.USD_PER_4K_IMAGE if str(size).upper() == "4K" else USD_PER_1K_IMAGE


def replace_retry(tmp, dst, tries=60):
    """os.replace that waits out a Windows scanner or indexer holding the file open for a
    moment (WinError 5 on a file written milliseconds ago). About three seconds at most."""
    for i in range(tries):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


# ================================================================== API key
def load_key():
    """GOOGLE_API_KEY from the environment, else GEMINI_API_KEY (copied into GOOGLE_API_KEY,
    which is what _render_common reads), else ./.env, else <skill folder>/.env. Returns where
    it came from, or None. The key itself is never printed."""
    if os.environ.get("GOOGLE_API_KEY", "").strip():
        return "environment (GOOGLE_API_KEY)"
    if os.environ.get("GEMINI_API_KEY", "").strip():
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"].strip()
        return "environment (GEMINI_API_KEY)"
    cands = [(os.path.join(os.getcwd(), ".env"), ".env in the current folder"),
             (os.path.join(SKILL_DIR, ".env"), ".env in the skill folder")]
    for p, label in cands:
        if not os.path.isfile(p):
            continue
        found = {}
        with open(p, encoding="utf-8-sig") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                k = k.strip()
                if k.startswith("export "):
                    k = k[len("export "):].strip()
                if sep and k in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
                    v = v.strip().strip('"').strip("'")
                    if v:
                        found.setdefault(k, v)
        v = found.get("GOOGLE_API_KEY") or found.get("GEMINI_API_KEY")
        if v:
            os.environ["GOOGLE_API_KEY"] = v
            return label
    return None


MISSING_KEY = """!! No Gemini API key found. Looked in: the environment (GOOGLE_API_KEY, then
   GEMINI_API_KEY), %s, and %s.
   Set it yourself as a USER environment variable - never paste it into the chat:
     Windows : Settings > System > About > Advanced system settings > Environment Variables
               > User variables > New...   Name: GOOGLE_API_KEY   Value: your key
               (or, in your own PowerShell window:
                [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "<your key>", "User") )
     macOS / Linux : add   export GOOGLE_API_KEY="<your key>"   to ~/.zshrc or ~/.bashrc
   Then restart Claude Code (a running session does not see new variables) and run
     python render.py check
   Prefer the environment variable to a .env file, and never put a .env inside a skill
   folder that is copied, zipped or uploaded.
   Create the key at aistudio.google.com/apikey in a billing-enabled Google Cloud project
   that has a monthly spend cap (aistudio.google.com/spend)."""


class _Redactor:
    """A stdout / stderr wrapper that masks the API key. A second safeguard: the vendored
    generate() puts the key in its URL and prints exception text, so if any library error
    ever echoes that URL, the key still never reaches the transcript."""

    def __init__(self, stream, secret):
        self._stream, self._secret = stream, secret

    def write(self, s):
        if self._secret and isinstance(s, str):
            s = s.replace(self._secret, "***")
        return self._stream.write(s)

    def __getattr__(self, name):
        return getattr(self._stream, name)


def redact_key_in_output():
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if not isinstance(stream, _Redactor):
            setattr(sys, name, _Redactor(stream, key))


def require_key():
    label = load_key()
    if not label:
        raise Failed(MISSING_KEY % (os.path.join(os.getcwd(), ".env"),
                                    os.path.join(SKILL_DIR, ".env")))
    redact_key_in_output()
    # _render_common puts the key in the URL; a space or control character would make urllib
    # raise an error whose text contains that URL. Refuse such a key without showing it.
    if not re.fullmatch(r"[A-Za-z0-9._~-]+", os.environ["GOOGLE_API_KEY"]):
        raise Failed("the API key from %s contains characters that cannot be part of a key "
                     "(a space, quote or line break?) - re-copy it from AI Studio and set it "
                     "again. Its value is not shown." % label)
    return label


# ======================================================= what each HTTP call cost
# generate() reports every failure the same way (it prints and returns None), but they cost
# different amounts: an HTTP 200 is billed whether or not it carries an image; an HTTP error
# response is normally not billed; a request that never left this machine (bad URL, refused
# connection, DNS failure) cannot be. This wrapper records what each urlopen() call generate()
# makes actually did, without touching the vendored file.
CALLS = []                                      # [("ok"|"http"|"not_sent"|"unknown", code)]
_real_urlopen = urllib.request.urlopen


def _tracked_urlopen(*args, **kwargs):
    try:
        r = _real_urlopen(*args, **kwargs)
    except urllib.error.HTTPError as e:         # a response came back: 4xx / 5xx
        CALLS.append(("http", e.code))
        raise
    except (urllib.error.URLError, http.client.InvalidURL, ValueError):
        CALLS.append(("not_sent", None))        # failed while connecting or sending
        raise
    except BaseException:
        CALLS.append(("unknown", None))         # sent, then no response read (timeout...)
        raise
    CALLS.append(("ok", getattr(r, "status", 200)))
    return r


def track_calls():
    urllib.request.urlopen = _tracked_urlopen


def test_endpoint():
    """Tests only: RENDER_TEST_ENDPOINT points every call at a LOCAL mock server."""
    ep = os.environ.get("RENDER_TEST_ENDPOINT", "").strip()
    if not ep:
        return None
    u = urllib.parse.urlparse(ep)
    if (u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost", "::1")
            or u.path not in ("", "/") or u.query or u.params or u.fragment):
        raise Failed("RENDER_TEST_ENDPOINT must be http://127.0.0.1:<port> (a local mock); "
                     "refusing to send a key anywhere else")
    return ep.rstrip("/")


def api_base():
    return test_endpoint() or GOOGLE_API_BASE


def point_generate_at_endpoint():
    ep = test_endpoint()
    if ep:
        rc.URL = ep + "/v1beta/models/%s:generateContent?key=%s"
        print("   TEST ENDPOINT: every call goes to the local mock at %s" % ep, flush=True)


# ================================================================ image prep
ALPHA_MODES = ("RGBA", "LA", "PA", "RGBa", "La")


def flatten(im):
    """RGB copy; transparency lands on white, which is what a sketch's void usually is."""
    if im.mode in ALPHA_MODES or "transparency" in im.info:
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def plan_pad(w, h):
    """Supported ratio reachable with the least padding, and which axis grows."""
    r = w / h
    best = None
    for name, R in RATIOS.items():
        if R >= r:
            frac, axis = (h * R - w) / w, "x"
        else:
            frac, axis = (w / R - h) / h, "y"
        if best is None or frac < best[0]:
            best = (frac, name, axis)
    return best[1], best[2], best[0]


def pad_to(im, dst):
    """Edge-extend im to the planned ratio and save it. Returns (ratio name, axis that
    grew or None, box) where box is the source rectangle inside the canvas as fractions."""
    w, h = im.size
    name, axis, frac = plan_pad(w, h)
    R = RATIOS[name]
    if axis == "x":
        W, H = int(round(h * R)), h
    else:
        W, H = w, int(round(w / R))
    W, H = max(W, w), max(H, h)
    l, t = (W - w) // 2, (H - h) // 2
    c = Image.new("RGB", (W, H))
    c.paste(im, (l, t))
    if axis == "x" and W > w:
        if l:
            c.paste(im.crop((0, 0, 1, h)).resize((l, h)), (0, 0))
        if W - w - l:
            c.paste(im.crop((w - 1, 0, w, h)).resize((W - w - l, h)), (l + w, 0))
    elif axis == "y" and H > h:
        if t:
            c.paste(im.crop((0, 0, w, 1)).resize((w, t)), (0, 0))
        if H - h - t:
            c.paste(im.crop((0, h - 1, w, h)).resize((w, H - h - t)), (0, t + h))
    c.save(dst, quality=96)
    grew = axis if (W > w or H > h) else None
    return name, grew, (l / W, t / H, (l + w) / W, (t + h) / H)


def crop_back(raw, box, out, src_ratio):
    """Cut the source's rectangle back out of the render and restore its exact ratio
    (the model's frames land up to ~1% off nominal). Returns the delivered size."""
    im = Image.open(raw).convert("RGB")
    W, H = im.size
    rect = (int(round(box[0] * W)), int(round(box[1] * H)),
            int(round(box[2] * W)), int(round(box[3] * H)))
    crop = im.crop(rect)
    w = crop.width
    h = max(1, int(round(w / src_ratio)))
    if h != crop.height:
        crop = crop.resize((w, h), Image.LANCZOS)
    crop.save(out)
    return crop.size


def shrink_for_feed(im):
    sw, sh = im.size
    if max(im.size) > FEED_MAX_EDGE:
        s = FEED_MAX_EDGE / max(im.size)
        im = im.resize((max(1, round(sw * s)), max(1, round(sh * s))), Image.LANCZOS)
    return im


def prepare_feed(src_path, work, tag):
    """Source file -> padded feed for the model. Returns (feed path, ratio, grew, box,
    source w/h ratio)."""
    im = flatten(ImageOps.exif_transpose(Image.open(src_path)))
    sw, sh = im.size
    im = shrink_for_feed(im)
    os.makedirs(work, exist_ok=True)
    feed = os.path.join(work, tag + "_padded.jpg")
    ratio, grew, box = pad_to(im, feed)
    return feed, ratio, grew, box, sw / sh


def fake_render(feed, out_base, size, notes=""):
    """DRY RUN stand-in: the padded feed at the model's rough output scale, toned and
    stamped so it can never be mistaken for a delivery. Goes through the same crop-back
    and sheet path as a real render. Notes containing "[drift]" return a 4:3 frame, to
    exercise the re-frame guard without an API call."""
    from PIL import ImageDraw, ImageFilter
    im = Image.open(feed).convert("RGB")
    long_edge = 3840 if size == "4K" else 1024
    if "[drift]" in (notes or "").lower():
        im = im.resize((long_edge, long_edge * 3 // 4), Image.LANCZOS)
    else:
        s = long_edge / max(im.size)
        im = im.resize((max(1, round(im.size[0] * s)), max(1, round(im.size[1] * s))),
                       Image.LANCZOS)
    im = ImageOps.autocontrast(im).filter(ImageFilter.GaussianBlur(0.4))
    im = Image.blend(im, ImageOps.colorize(ImageOps.grayscale(im), (40, 30, 20),
                                           (255, 245, 225)), 0.35)
    d = ImageDraw.Draw(im)
    f = cs.font(cs.GOTHICB, max(18, im.size[0] // 28))
    d.text((im.size[0] // 40, im.size[1] // 40), "DRY RUN - no API call made", font=f,
           fill=(214, 48, 32))
    time.sleep(2)
    dst = out_base + ".png"
    im.save(dst)
    return dst


def feather_mask(w, h, left, right, top, bottom, feather=FEATHER):
    """Pillow port of the numpy mask in patch_p18_1k.py / render_p19_1k.py: opaque,
    with a linear 0 -> 1 ramp of `feather` px on every edge that lies inside the frame."""
    ramp = [i / (feather - 1) for i in range(feather)]          # np.linspace(0, 1, FEATHER)
    cx, cy = [1.0] * w, [1.0] * h
    for i in range(feather):
        if left:
            cx[i] *= ramp[i]
        if right:
            cx[w - feather + i] *= ramp[feather - 1 - i]
        if top:
            cy[i] *= ramp[i]
        if bottom:
            cy[h - feather + i] *= ramp[feather - 1 - i]
    m = Image.new("L", (w, h))
    m.putdata([int(cx[x] * cy[y] * 255) for y in range(h) for x in range(w)])
    return m


# ================================================================== input
def probe_input(path):
    """What the input is, without writing anything. Raises Failed with a plain message."""
    if not os.path.isfile(path):
        raise Failed("no such file: %s" % path)
    with open(path, "rb") as f:
        head = f.read(5)
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "pdf" or head == b"%PDF-":
        try:
            import fitz
        except ImportError:
            raise Failed("PDF input needs PyMuPDF (pip install pymupdf) - or export page 1 of "
                         "the PDF as a PNG and render that")
        try:
            doc = fitz.open(path)
            if doc.page_count < 1:
                raise ValueError("no pages")
            r = doc[0].rect
            area_pt = float(r.width) * float(r.height)
            if area_pt <= 0:
                raise ValueError("empty page")
            # The page size sets the pixmap size; a hostile MediaBox must not set it to GBs.
            dpi = int(min(200.0, 72.0 * math.sqrt(PDF_PIXEL_CAP / area_pt)))
            pages = doc.page_count
        except Exception as e:
            raise Failed("could not read the PDF: %s" % e)
        if dpi < 24:
            raise Failed("PDF page is too large to rasterise")
        return {"kind": "pdf", "dpi": dpi, "pages": pages, "store_png": True,
                "size": (int(round(r.width * dpi / 72.0)), int(round(r.height * dpi / 72.0)))}
    try:
        im = Image.open(path)
    except Image.DecompressionBombError:
        raise Failed("image is over %d megapixels" % (PIXEL_CAP // 1_000_000))
    except Exception:
        raise Failed("unsupported file - use a JPG, PNG, WEBP or PDF")
    with im:
        w, h = im.size
        if w * h > PIXEL_CAP:
            raise Failed("image is over %d megapixels" % (PIXEL_CAP // 1_000_000))
        fmt = (im.format or "").lower()
        if fmt == "jpeg":
            fmt = "jpg"
        orientation = 1
        try:
            orientation = int(im.getexif().get(0x0112, 1) or 1)
        except Exception:
            pass
        # Decode it now (as the local app's decode_upload does): a truncated or corrupt file must
        # fail here with a plain message, before a job, a key or a spend is involved.
        try:
            im.load()
        except Exception as e:
            raise Failed("the image could not be decoded (%s: %s) - the file is truncated or "
                         "corrupt; re-export it" % (type(e).__name__, e))
        transparent = has_transparency(im)
    if orientation in (5, 6, 7, 8):
        w, h = h, w
    if min(w, h) < 64:
        raise Failed("image is too small to render (%dx%d)" % (w, h))
    why = []
    if orientation != 1:
        why.append("EXIF-rotated")
    if fmt not in IMAGE_EXT:
        why.append("%s is not png/jpg/webp" % (fmt or "format"))
    if transparent:
        # The sheet builder reads a source with .convert("RGB"), which turns transparent
        # pixels black; the model is fed the image flattened on white. Store that flattened
        # PNG as the source of record so the sheet shows what the model actually saw.
        why.append("transparent background flattened on white")
    return {"kind": "image", "pages": None, "size": (w, h), "store_png": bool(why),
            "why": "; ".join(why) or None}


def has_transparency(im):
    """Does the image have any pixel that is not fully opaque?"""
    try:
        if im.mode in ALPHA_MODES:
            return im.getchannel("A").getextrema()[0] < 255
        if "transparency" in im.info:
            return im.convert("RGBA").getchannel("A").getextrema()[0] < 255
    except Exception:
        return True                       # cannot tell: flatten it, which is always safe
    return False


def materialise_source(inp, probe, work, stem):
    """The source of record. Images are kept as they are (their bytes are the true original
    for the sheet) unless they carry an EXIF rotation, have a transparent background or are
    not png/jpg/webp; then an upright PNG flattened on white in _work is. A PDF becomes a PNG
    of its first page."""
    if not probe["store_png"]:
        return inp
    os.makedirs(work, exist_ok=True)
    dst = os.path.join(work, "%s_source.png" % stem)
    if probe["kind"] == "pdf":
        import fitz
        doc = fitz.open(inp)
        pix = doc[0].get_pixmap(dpi=probe["dpi"], alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        im = Image.open(inp)
        im.load()
        im = ImageOps.exif_transpose(im) or im
    tmp = dst + ".part"
    flatten(im).save(tmp, format="PNG")
    replace_retry(tmp, dst)
    return dst


def default_out(inp):
    """Sibling '03 Output' when the input sits in an '... Input' folder, else
    '<input folder>/03 Output'."""
    d = os.path.dirname(os.path.abspath(inp))
    if "input" in os.path.basename(d).lower():
        return os.path.join(os.path.dirname(d), "03 Output")
    return os.path.join(d, "03 Output")


def inside(path, folder):
    a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:                          # another drive on Windows
        return False


def check_out_dir(out, given):
    """Nothing is ever written inside the skill folder: it may be synced, zipped or uploaded,
    and ledgers, raw frames and prompts do not belong in it."""
    if inside(out, SKILL_DIR):
        raise Refused("the output folder %s is inside the skill folder. %s Pass --out with a "
                      "folder outside %s - for the bundled test sketch, a scratch folder such as "
                      "\"%s\"." % (out, "" if given else "(It is the default for an input that "
                                   "lives in the skill folder.)", SKILL_DIR,
                                   os.path.join(tempfile.gettempdir(), "render-test",
                                                "03 Output")))


# ================================================================== notes / brief
def read_notes(a):
    """--notes or --notes-file (argparse makes them mutually exclusive)."""
    if getattr(a, "notes_file", None):
        try:
            with open(a.notes_file, encoding="utf-8-sig") as f:
                return f.read()
        except OSError as e:
            raise Refused("could not read the notes file %s: %s" % (a.notes_file, e))
    return getattr(a, "notes", None) or ""


# A revise or patch keeps the camera; notes asking it to move cannot be honoured and only
# spend money on a self-contradictory prompt (the header says to keep the camera identical).
CAMERA_WORDS = re.compile(
    r"\b((?:move|lower|raise|tilt|rotate|turn|swing|pull back) the camera|"
    r"camera (?:angle|position|height|lower|higher)|"
    r"viewpoint|vantage point|point of view|zoom(?:ed)? (?:in|out)|re-?frame|"
    r"re-?compose|crop (?:in|out|to)|wider (?:shot|view|angle)|closer (?:shot|view)|"
    r"(?:other|garden|rear|back|opposite|street) side of the (?:villa|house|building)|"
    r"from the (?:garden|rear|back|street|other) side|bird'?s[- ]eye|eye[- ]level|"
    r"aerial view|(?:lower|higher|different|new) (?:camera )?angle|three-quarter view)\b", re.I)


def warn_camera_change(notes, action):
    hits = sorted({m.group(0).lower() for m in CAMERA_WORDS.finditer(notes or "")})
    if hits:
        print("!! CAMERA / FRAMING WORDS in the %s notes (%s). A %s keeps the camera, framing "
              "and composition exactly; it cannot show another side, angle or zoom. If the "
              "user wants a different view, do not spend: ask for a new export of that view "
              "from the model and render it as a new job." % (action, ", ".join(hits), action),
              flush=True)


def compose_notes(a):
    """--notes / --notes-file, or the four fields composed as the hosted version does."""
    free = read_notes(a).strip()
    fields = {"materials": a.materials or "", "lighting": a.lighting or "",
              "environment": a.environment or "", "other_notes": a.other or ""}
    if free and any(v.strip() for v in fields.values()):
        raise Refused("use either --notes / --notes-file or the four field flags "
                      "(--materials --lighting --environment --other), not both")
    if free:
        notes = free
    else:
        # From the hosted version (routes_user.py) _receive_render.
        notes = "\n".join("%s: %s" % (lab, fields[k].strip()) for lab, k in
                          (("Materials", "materials"), ("Lighting", "lighting"), ("Environment", "environment"),
                           ("Other", "other_notes")) if fields.get(k, "").strip())
    if len(notes) > NOTES_MAX:
        raise Refused("notes are %d characters; the limit is %d - shorten them"
                      % (len(notes), NOTES_MAX))
    return notes


def _clean_list(v, max_items, max_len):
    """From the hosted version (providers.py)."""
    out = []
    for item in (v if isinstance(v, list) else []):
        if isinstance(item, str):
            s = re.sub(r"[\x00-\x1f\x7f]", " ", item).strip()
            if s:
                out.append(s[:max_len])
        if len(out) >= max_items:
            break
    return out


def _brief_text(brief):
    """From the hosted version (engine.py)."""
    if not brief or not brief.get("elements"):
        return ""
    t = ("\n\nSKETCH ELEMENT INVENTORY (an automatic analysis of the input; treat it as a checklist: every listed "
         "element must appear, in the same place and proportion, and nothing else may be added):\n"
         + "\n".join("- " + e for e in brief["elements"]))
    if brief.get("finishes"):
        t += "\nFINISHES TO USE:\n" + "\n".join("- " + e for e in brief["finishes"])
    if brief.get("cautions"):
        t += "\nTAKE SPECIAL CARE:\n" + "\n".join("- " + e for e in brief["cautions"])
    return t[:3000]


BRIEF_LIMITS = (("elements", 30, 160), ("finishes", 15, 120), ("cautions", 10, 160))


def load_brief(path):
    """A per-view brief written by Claude: {"elements": [...], "finishes": [...],
    "cautions": [...]}. Refused (not silently cut) when it breaks the hosted version's limits."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            obj = json.load(f)
    except (OSError, ValueError) as e:
        raise Refused("could not read the brief %s: %s" % (path, e))
    if not isinstance(obj, dict):
        raise Refused("the brief must be a JSON object with elements / finishes / cautions")
    unknown = sorted(set(obj) - {k for k, _, _ in BRIEF_LIMITS})
    if unknown:
        raise Refused("unknown key(s) in the brief: %s (allowed: elements, finishes, cautions)"
                      % ", ".join(unknown))
    for k, n, ln in BRIEF_LIMITS:
        v = obj.get(k, [])
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise Refused("brief '%s' must be a list of strings" % k)
        if len(v) > n:
            raise Refused("brief '%s' has %d items; the limit is %d" % (k, len(v), n))
        for s in v:
            if len(s.strip()) > ln:
                raise Refused("brief '%s' item is %d characters (limit %d): %s"
                              % (k, len(s.strip()), ln, s.strip()[:80] + "..."))
    brief = {k: _clean_list(obj.get(k), n, ln) for k, n, ln in BRIEF_LIMITS}
    if not brief["elements"]:
        raise Refused("the brief needs at least one entry in 'elements'")
    if len(_brief_text(brief)) >= 3000:
        raise Refused("the brief block reaches the 3000-character cap and would be cut - "
                      "shorten it")
    return brief


# ================================================================== prompts
def build_prompt(kind, notes, grew, brief=None, fidelity=None):
    """The local app's build_prompt, plus the hosted version's inventory block for a render, plus the
    terracotta-free fidelity brief when the caller passes one."""
    notes = (notes or "").strip()
    if kind == "render":
        p = fidelity or rc.FIDELITY_PROMPT
        if notes:
            p += ("\n\nUSER NOTES - explicit instructions for this render. Apply them "
                  "exactly and treat them as the only permitted departures from the input "
                  "beyond material realism:\n" + notes)
        p += _brief_text(brief)
    elif kind == "revise":
        p = REVISE_HEADER + "\n\n" + (notes or "(no changes given - reproduce the image)")
    else:                                                       # 4k
        p = "\n\n".join([rc.UPSCALE_PROMPT, LOCKED_FINISHES, UPSCALE_LOOK])
        if notes:
            p += "\n\nFor reference, the approved image was made with these notes:\n" + notes
    if grew:
        p += CANVAS_NOTE.format(where="left and right" if grew == "x" else "top and bottom")
    if kind == "render":
        p += ("\n\nFINAL AND OVERRIDING - FRAMING: same camera, same framing, same geometry "
              "as the input, nothing added and nothing removed. Output ONE photograph.")
    else:
        p += "\n\nOutput ONE photograph with exactly the same framing."
    return p


LATER_CHANGES = "Later changes, already made in the approved image (do not apply them again):"


def upscale_notes(job, cur):
    """The notes the 4K prompt carries 'for reference'. The local app passes the approved pass's own
    notes; for an approved revision or patch those are an imperative edit ("add a second
    lounger") that a resolution pass could apply a second time, and the first render's
    material notes would be lost. So: the lineage's render notes, then each later change
    marked as already made. For an approved first render this is exactly the local app's text."""
    by_file = {p["file"]: p for p in job["passes"] if p.get("file") and p["status"] == "done"}
    chain, p, seen = [], cur, set()
    while p is not None and id(p) not in seen:
        seen.add(id(p))
        chain.append(p)
        if p["kind"] == "render":
            break
        p = by_file.get(p.get("before"))
    chain.reverse()
    first = chain[0] if chain and chain[0]["kind"] == "render" else None
    parts = [first["notes"].strip()] if first and (first.get("notes") or "").strip() else []
    later = [" ".join(q["notes"].split()) for q in chain if q is not first
             and (q.get("notes") or "").strip()]
    if later:
        parts.append(LATER_CHANGES + "\n" + "\n".join("- " + n for n in later))
    return "\n".join(parts)


def build_patch_prompt(notes, grew):
    """patch_p18_1k.py HEADER + change [+ the local app's CANVAS_NOTE] + TAIL. (project 18's
    own canvas note adds a sentence about brief percentages, which a patch note has none of.)"""
    prompt = HEADER + "\n\n" + notes.strip()
    if grew:
        prompt += CANVAS_NOTE.format(where="left and right" if grew == "x" else "top and bottom")
    prompt += TAIL
    return prompt


# ================================================================== job ledger
def jobs_dir(out):
    return os.path.join(out, "_jobs")


def job_path(out, stem):
    return os.path.join(jobs_dir(out), stem + ".json")


def load_job(path):
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    if not (isinstance(j, dict) and isinstance(j.get("passes"), list) and j.get("stem")):
        raise ValueError("not a job record")
    return j


def save_job(out, job):
    dst = job_path(out, job["stem"])
    tmp = "%s.%d.tmp" % (dst, os.getpid())
    os.makedirs(jobs_dir(out), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1, ensure_ascii=False)
    replace_retry(tmp, dst)


def all_jobs(out):
    jobs = []
    for p in sorted(glob.glob(os.path.join(jobs_dir(out), "*.json"))):
        try:
            jobs.append(load_job(p))
        except Exception as e:
            print("!! skipping job file %s: %s" % (os.path.basename(p), e))
    return jobs


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_or_new_job(out, name, inp, digest):
    """The job for this input under this name, or a free name for a new one: a second
    render of the same, unchanged input is a new pass of the same job; a different input -
    or the same path re-exported with new content - gets 'name (2)'."""
    cand, i = name, 1
    while os.path.exists(job_path(out, cand)):
        try:
            j = load_job(job_path(out, cand))
            if same_path(j.get("input", ""), inp):
                if j.get("input_sha256") in (None, digest):
                    return cand, j
                print("   the input changed since job '%s' was started - starting a new job"
                      % cand, flush=True)
        except Exception:
            pass
        i += 1
        cand = "%s (%d)" % (name, i)
    return cand, None


def find_job_for_file(path):
    """(out, job, pass index) of a delivered file, or Refused."""
    f = os.path.abspath(path)
    if not os.path.isfile(f):
        raise Failed("no such file: %s" % path)
    out = os.path.dirname(f)
    for j in all_jobs(out):
        for i, ps in enumerate(j["passes"]):
            if ps.get("file") and same_path(absp(out, ps["file"]), f):
                return out, j, i
    raise Refused("%s is not a render this tool delivered (no entry in %s). revise, patch, "
                  "upscale and sheet work only on files render.py made; to start from this "
                  "image, use 'render'." % (os.path.basename(f), jobs_dir(out)))


def current_of(job, live_only=False):
    """The latest done pass that is not a 4K - the only file that may be revised, patched or
    approved. A live pass never starts from a dry-run stand-in."""
    done = [p for p in job["passes"] if p["status"] == "done" and p["kind"] != "4k"
            and not (live_only and p.get("dry_run"))]
    return done[-1] if done else None


def same_shape_as_source(out, job, ps):
    """Is the delivered file the shape of the original source? Read off the file itself,
    so it holds even for a job record that was edited by hand."""
    try:
        with Image.open(absp(out, ps["file"])) as im:
            w, h = im.size
        sw, sh = job["source_size"]
        return abs((w / h) / (sw / sh) - 1) <= cs.ASPECT_TOL
    except Exception:
        return False


def sheet_path_for(out, ps):
    return os.path.join(out, "_Before After - %s.jpg" % ps["out_stem"])


def adopt_sheet(out, job, ps):
    """A sheet built by hand at the expected path counts."""
    if ps.get("sheet") or not ps.get("out_stem"):
        return
    p = sheet_path_for(out, ps)
    if os.path.isfile(p):
        ps["sheet"], ps["error"] = rel(out, p), None
        save_job(out, job)


def gate_current(out, job, idx, live, action):
    """Refuse unless the named file is the current pass and its framing is sound."""
    ps = job["passes"][idx]
    name = os.path.basename(ps["file"])
    if ps["kind"] == "4k":
        raise Refused("%s is a 4K delivery - 4K files are final and are never revised, patched "
                      "or upscaled again. Work on the approved 1K file instead." % name)
    if live and ps.get("dry_run"):
        raise Refused("%s is a DRY-RUN stand-in (no API call made); a live %s cannot start "
                      "from it. Render live from the source first." % (name, action))
    cur = current_of(job, live_only=live)
    if cur is None or cur is not ps:
        raise Refused("%s is not the current render of job '%s' - the current one is %s. "
                      "Name the exact current file." % (
                          name, job["stem"], os.path.basename(cur["file"]) if cur else "(none)"))
    if "tier" in (ps.get("warning_kind") or ""):
        raise Refused("%s came back at the wrong size tier (%s). The size parameter may have "
                      "been ignored: stop, tell the user, and run no further passes until a "
                      "test render comes back at the tier asked for." % (name, ps["warning"]))
    if ps.get("warning") or not same_shape_as_source(out, job, ps):
        raise Refused("%s was re-framed (its framing differs from the source): %s %s would "
                      "carry the wrong framing forward. Render again from the source."
                      % (name, "approving" if action == "upscale" else action + "ing", name))
    return ps


def lock_folder(out):
    """One writing command per output folder: two would pick the same free name or rewrite
    each other's job record. Released by the OS when the process ends, however it ends."""
    os.makedirs(jobs_dir(out), exist_ok=True)
    fd = os.open(os.path.join(jobs_dir(out), ".lock"), os.O_RDWR | os.O_CREAT)
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise Failed("another render.py command is working in %s - wait for it to finish"
                     % out)
    lock_folder.fds.append(fd)


lock_folder.fds = []


# ================================================================== the passes
def new_pass(out, kind, size, before, notes, brief, mode, out_stem, title, labels, model,
             sheet_before=None):
    return {"kind": kind, "size": size, "status": "running", "before": rel(out, before),
            "sheet_before": rel(out, sheet_before) if sheet_before else None,
            "file": None, "raw": None, "sheet": None, "prompt_file": None,
            "attempts": 0, "calls": 0, "http_errors": 0, "not_sent": 0, "uncertain": 0,
            "cost_usd": 0.0, "cost_inr": 0.0, "warning": None, "warning_kind": None,
            "error": None, "notes": notes or "", "brief": brief, "dry_run": mode == "dry",
            "started": now(), "finished": None, "seconds": None, "model": model,
            "out_stem": out_stem, "title": title, "labels": list(labels),
            "ratio": None, "grew": None, "box": None, "src_ratio": None, "feed": None}


def pass_cost(ps):
    """List-price estimate of a pass: billed attempts (HTTP 200 responses, plus any sent
    attempt whose response was never read) at the requested tier; a frame that came back at
    another tier is priced at that tier. HTTP error responses and requests that never left
    the machine cost nothing."""
    if ps.get("dry_run"):
        return 0.0
    n = ps.get("attempts") or 0
    if n and ps.get("delivered_tier"):
        return (n - 1) * price(ps["size"]) + price(ps["delivered_tier"])
    return n * price(ps["size"])


def set_cost(ps):
    cost = pass_cost(ps)
    ps["cost_usd"], ps["cost_inr"] = round(cost, 4), round(cost * INR_PER_USD, 1)
    return cost


def attempts_summary(ps):
    parts = ["%d billed" % (ps.get("attempts") or 0)]
    if ps.get("uncertain"):
        parts.append("%d of them sent with no response read, counted as billed to be safe"
                     % ps["uncertain"])
    if ps.get("http_errors"):
        parts.append("%d HTTP error response(s), not billed" % ps["http_errors"])
    if ps.get("not_sent"):
        parts.append("%d never left this machine" % ps["not_sent"])
    return ", ".join(parts)


def finish_pass(out, job, ps, raw, t0, final_override=None):
    """Raw model frame -> delivered file + comparison sheet + pass record."""
    out_stem = ps["out_stem"]
    before = absp(out, ps.get("sheet_before") or ps["before"])
    final = os.path.join(out, out_stem + ".png")
    warnings, kinds = [], []
    with Image.open(raw) as im:
        W, H = im.size
    if not ps.get("dry_run"):
        # The vendored helper only prints a warning when the frame is not the tier asked for
        # (a 4K-sized frame for a 1K request is billed ~1.8x). Record it on the pass as well,
        # so the exit code, the report and 'status' all carry it.
        got_tier = rc.size_tier(W, H)
        if got_tier != ps["size"]:
            ps["delivered_tier"] = got_tier
            warnings.append("the API returned a %s-sized frame (%dx%d) for a %s request - the "
                            "size parameter may have been ignored; priced at the %s rate. Stop "
                            "and tell the user: run no further passes until a test render comes "
                            "back at the tier asked for." % (got_tier, W, H, ps["size"], got_tier))
            kinds.append("tier")
    lineage = ("this image is %.3f:1 but the upload is %.3f:1 - it descends from a re-framed "
               "render. Render again from the source; this one cannot be revised or approved "
               "for 4K.")
    if final_override is not None:                   # patch: the composite is already built
        final_override.save(final)
        size_px = final_override.size
        sw, sh = job["source_size"]
        got, want = size_px[0] / size_px[1], sw / sh
        if abs(got / want - 1) > cs.ASPECT_TOL:
            warnings.append(lineage % (got, want))
            kinds.append("lineage")
    else:
        drift = abs((W / H) / RATIOS[ps["ratio"]] - 1)
        if drift > cs.ASPECT_TOL:
            # The model re-framed. Cutting the source box out of a differently shaped frame
            # would select the wrong region and stretching it back would hide the change, so
            # the frame is delivered whole and the sheet's aspect flag does its job.
            Image.open(raw).convert("RGB").save(final)
            size_px = (W, H)
            warnings.append("the model returned a %.3f:1 frame for a %s request - it re-framed "
                            "instead of rendering in place. Delivered uncropped so nothing is "
                            "lost; the sheet flags the changed framing. Render again from the "
                            "source; this one cannot be revised or approved for 4K."
                            % (W / H, ps["ratio"]))
            kinds.append("reframe")
        else:
            size_px = crop_back(raw, ps["box"], final, ps["src_ratio"])
            # Framing belongs to the whole lineage, not to one hop: a revision or a 4K of a
            # re-framed render matches its own before perfectly and is still wrong. So every
            # delivery is also held against the shape of the original upload.
            sw, sh = job["source_size"]
            got, want = size_px[0] / size_px[1], sw / sh
            if abs(got / want - 1) > cs.ASPECT_TOL:
                warnings.append(lineage % (got, want))
                kinds.append("lineage")
    # _render_common recorded feed->raw; the delivered pair is the true before against the
    # delivered file, so drop that entry and write the sheet now.
    rc.forget(raw)
    sheet_path = os.path.join(out, "_Before After - %s.jpg" % out_stem)
    written = rc.write_comparison_sheet(out=sheet_path, title=ps["title"],
                                        before_label=ps["labels"][0],
                                        after_label=ps["labels"][1],
                                        pairs=[(out_stem, before, final)])
    ps.update(status="done", file=rel(out, final), raw=rel(out, raw),
              sheet=rel(out, written[0]) if written else None,
              finished=now(), seconds=round(time.time() - t0, 1),
              warning=" ALSO: ".join(warnings) or None,
              warning_kind="+".join(kinds) or None,
              error=None if written else "render OK but the comparison sheet failed - "
                                         "run 'render.py sheet <file>' before delivering; "
                                         "it cannot be approved for 4K until then")
    set_cost(ps)
    save_job(out, job)
    flags = ""
    if "reframe" in kinds or "lineage" in kinds:
        flags += "  !! re-framed by the model"
    if "tier" in kinds:
        flags += "  !! wrong size tier"
    print("   OK %s  %dx%d  (%.0fs)%s%s" % (os.path.basename(final), size_px[0], size_px[1],
                                           time.time() - t0, flags,
                                           "" if written else "  !! no sheet"), flush=True)


def tally(ps, entries):
    """Book what each HTTP call of one attempt did. Returns a one-line verdict or None."""
    verdict = None
    for kind, code in entries:
        ps["calls"] = ps.get("calls", 0) + 1
        if kind == "ok":
            ps["attempts"] += 1
            verdict = "HTTP 200: billed"
        elif kind == "unknown":
            ps["attempts"] += 1
            ps["uncertain"] = ps.get("uncertain", 0) + 1
            verdict = "sent, but no response was read: counted as billed to be safe"
        elif kind == "http":
            ps["http_errors"] = ps.get("http_errors", 0) + 1
            verdict = ("HTTP %s error response: booked as not billed (Google does not "
                       "normally charge a failed request)" % code)
        else:
            ps["not_sent"] = ps.get("not_sent", 0) + 1
            verdict = "the request never left this machine: not billed"
    set_cost(ps)
    return verdict


def call_model(out, job, ps, feed, prompt, out_base, size, ratio, confirmed, before, attempts,
               mode, notes):
    """One API call per loop turn so every attempt is counted, classified and priced.
    Returns the raw frame path or None; the counts live on the pass record."""
    if mode == "dry":
        return fake_render(feed, out_base, size, notes)
    raw = None
    for attempt in range(1, attempts + 1):
        print("   attempt %d/%d (each attempt is billed)" % (attempt, attempts), flush=True)
        n0 = len(CALLS)
        try:
            raw = rc.generate(feed, prompt, out_base, image_size=size, aspect=ratio,
                              model=MODEL, attempts=1, confirmed_4k=confirmed,
                              compare_src=before)
        finally:                       # also on SpendCapReached, errors and Ctrl+C
            new = CALLS[n0:]
            verdict = tally(ps, new)
            save_job(out, job)
        if verdict and not (raw and verdict.startswith("HTTP 200")):
            print("   -> %s" % (verdict if not verdict.startswith("HTTP 200") else
                                "HTTP 200 without an image: billed"), flush=True)
        if raw:
            break
        if attempt < attempts:
            last = new[-1] if new else None
            # The vendored helper waits 30 s after a 429 / 503 and 12 s otherwise.
            time.sleep(30 if last and last[0] == "http" and last[1] in (429, 503) else 12)
    return raw


def fail_pass(out, job, ps, t0, err, raw=None):
    kept = bool(raw and os.path.isfile(raw))
    ps.update(status="failed", finished=now(), seconds=round(time.time() - t0, 1),
              raw=rel(out, raw) if kept else ps.get("raw"),
              error=err + (" - the frame the model returned is kept at %s" % raw if kept else ""))
    cost = set_cost(ps)
    save_job(out, job)
    print("!! FAILED: %s" % ps["error"], flush=True)
    if not ps.get("dry_run") and ps.get("calls"):
        print("   attempts: %s - list price USD %.3f (INR %.0f)"
              % (attempts_summary(ps), cost, cost * INR_PER_USD), flush=True)
        print("   A rerun is a new spend: quote it to the user and wait for a new yes.",
              flush=True)


def report(out, ps):
    """What Claude needs to hand over: file, sheet, warning, cost."""
    print("\n---- result ----")
    print("file    : %s" % absp(out, ps["file"]))
    print("sheet   : %s" % (absp(out, ps["sheet"]) if ps.get("sheet") else
                            "MISSING - run: python render.py sheet \"%s\"" % absp(out, ps["file"])))
    if ps.get("warning"):
        print("WARNING : %s" % ps["warning"])
    if ps.get("error"):
        print("ERROR   : %s" % ps["error"])
    if ps.get("dry_run"):
        print("cost    : none (dry run - a stamped stand-in, not a render)")
    else:
        print("cost    : %s - list price USD %.3f (INR %.0f); the real bill is in AI Studio"
              % (attempts_summary(ps), ps["cost_usd"], ps["cost_inr"]))
    print("next    : open the sheet and review it with references/review-checklist.md before "
          "reporting.")
    return EXIT_ATTENTION if (ps.get("warning") or not ps.get("sheet")) else EXIT_OK


def run_pass(out, job, kind, size, before, notes, brief, out_stem, title, labels, mode,
             attempts, confirmed=False, fidelity=None, sheet_before=None):
    """render / revise / 4k: pad -> prompt -> model (or stand-in) -> crop back -> sheet."""
    work = os.path.join(out, "_work")
    if mode == "prompt":
        work = os.path.join(work, "prompt-only")
    feed, ratio, grew, box, src_ratio = prepare_feed(before, work, out_stem)
    prompt = build_prompt(kind, notes, grew, brief=brief, fidelity=fidelity)
    prompt_file = os.path.join(work, out_stem + "_prompt.txt")
    write_text(prompt_file, prompt)
    print("===== %s | %s | %s | %s canvas, pad %s | %s =====" % (
        job["stem"], kind, size, ratio, grew or "none",
        {"live": "LIVE - billed", "dry": "DRY RUN - no API call", "prompt": "PROMPT ONLY"}[mode]),
        flush=True)
    if mode == "prompt":
        return print_prompt(prompt, prompt_file, feed)
    t0 = time.time()
    out_base = os.path.join(out, "_work", out_stem + "_raw")
    ps = new_pass(out, kind, size, before, notes, brief, mode, out_stem, title, labels, MODEL,
                  sheet_before=sheet_before)
    ps.update(ratio=ratio, grew=grew, box=list(box), src_ratio=src_ratio,
              feed=rel(out, feed), prompt_file=rel(out, prompt_file),
              terracotta_example=(fidelity is None) if kind == "render" else None)
    job["passes"].append(ps)
    save_job(out, job)
    raw = None
    try:
        raw = call_model(out, job, ps, feed, prompt, out_base, size, ratio, confirmed,
                         before, attempts, mode, notes)
        if not raw:
            raise RuntimeError("the model returned no image (%s)" % attempts_summary(ps))
        ps["raw"] = rel(out, raw)               # on record first: this frame has been paid for
        save_job(out, job)
        finish_pass(out, job, ps, raw, t0)
    except rc.SpendCapReached as e:
        fail_pass(out, job, ps, t0, "SpendCapReached: %s" % e)
        return EXIT_ERROR
    except KeyboardInterrupt:
        fail_pass(out, job, ps, t0, "interrupted - a live attempt may already have been billed")
        return EXIT_ERROR
    except Exception as e:
        fail_pass(out, job, ps, t0, "%s: %s" % (type(e).__name__, e), raw)
        return EXIT_ERROR
    return report(out, ps)


def print_prompt(prompt, prompt_file, feed):
    print("feed    : %s" % feed)
    print("prompt  : %s (%d chars)" % (prompt_file, len(prompt)))
    print("----- prompt -----")
    print(prompt)
    print("----- end of prompt -----")
    print("PROMPT ONLY - nothing was sent, no key was read, no pass was recorded.")
    return EXIT_OK


# ================================================================ spend gate
def resolve_attempts(n):
    if n is None and ATTEMPTS_NOTE:
        print("!! " + ATTEMPTS_NOTE, flush=True)
    n = ATTEMPTS if n is None else n
    if n < 1:
        raise Refused("--attempts must be at least 1")
    if n > MAX_ATTEMPTS:
        raise Refused("%d attempts refused: every attempt is billed. Fix the prompt instead of "
                      "raising the retry count (max %d)." % (n, MAX_ATTEMPTS))
    return n


def estimate_lines(size, attempts):
    usd = attempts * price(size)
    return [
        "  images    : 1",
        "  tier      : %s" % size,
        "  attempts  : up to %d (each attempt is billed, including attempts that return no image)"
        % attempts,
        "  max cost  : USD %.3f (INR %.0f) at list price - USD %.3f per %s image, plus ~USD 0.0011 "
        "per input image" % (usd, usd * INR_PER_USD, price(size),
                             "4K" if size == "4K" else "1K/2K"),
        "  model     : %s (generateContent, %s)" % (MODEL, api_base()),
    ]


def estimate(kind, size, attempts, job_desc, before, out, out_stem):
    lines = (["SPEND GATE - nothing has been sent and no API key has been read.",
              "  job       : %s" % job_desc,
              "  pass      : %s from %s" % (kind, before)]
             + estimate_lines(size, attempts)
             + ["  output    : %s  (+ its comparison sheet)" % os.path.join(out, out_stem + ".png"),
                "Ask the user for an explicit yes - state the image count, the tier and the cost "
                "- then re-run with --spend-ok."])
    print("\n".join(lines), flush=True)
    return EXIT_SPEND_GATE


def mode_of(a):
    if getattr(a, "prompt_only", False):
        return "prompt"
    if getattr(a, "dry_run", False):
        return "dry"
    return "live"


def go_live(out):
    """Key and lock, in that order, for a live pass. Nothing before this sends anything."""
    label = require_key()
    point_generate_at_endpoint()
    track_calls()
    print("   key: %s (value not shown)" % label, flush=True)
    print("   this sends the drawing to Google's Gemini API (%s)" % api_base(), flush=True)
    lock_folder(out)


# ================================================================== commands
def cmd_render(a):
    inp = os.path.abspath(a.input)
    probe = probe_input(inp)
    orig, oprobe = None, None
    if a.original:
        # The input is a prepared copy (axis lines cleaned, labels erased, void pre-filled);
        # the sheet must still show the untouched export beside the delivery.
        orig = os.path.abspath(a.original)
        if same_path(orig, inp):
            raise Refused("--original names the input itself - leave it out")
        oprobe = probe_input(orig)
        (w, h), (ow, oh) = probe["size"], oprobe["size"]
        if abs((ow / oh) / (w / h) - 1) > cs.ASPECT_TOL:
            raise Refused("--original is %.3f:1 but the input is %.3f:1. --original is for a "
                          "prepared copy of the same export (same frame, lines cleaned, labels "
                          "erased, void pre-filled), not for a crop or another view - a cropped "
                          "panel is its own source." % (ow / oh, w / h))
    notes = compose_notes(a)
    brief = load_brief(a.brief) if a.brief else None
    size = rc.check_image_size(a.size or DRAFT_SIZE)       # refuses 4K before anything else
    attempts = resolve_attempts(a.attempts)
    mode = mode_of(a)
    out = os.path.abspath(a.out) if a.out else default_out(inp)
    check_out_dir(out, bool(a.out))
    name = safe_name(a.name) if a.name else safe_name(os.path.basename(inp), strip_ext=True)
    fidelity = FIDELITY if a.no_terracotta_example else None
    digest = file_sha256(inp)

    stem, job = find_or_new_job(out, name, inp, digest)
    out_stem = free_stem(out, "%s_%s" % (stem, size))
    if mode == "live" and not a.spend_ok:
        desc = "%s (%s)" % (stem, "existing job, pass %d" % (len(job["passes"]) + 1) if job
                            else "new job")
        return estimate("render", size, attempts, desc, inp, out, out_stem)
    if mode == "live":
        go_live(out)
    elif mode == "dry":
        lock_folder(out)
    if probe.get("pages"):
        print("   PDF page 1 of %d is the source (rasterised at %d dpi)"
              % (probe["pages"], probe["dpi"]))
    if mode == "prompt":
        work = os.path.join(out, "_work", "prompt-only")
        src = materialise_source(inp, probe, work, stem)
        job = job or {"stem": stem, "passes": []}
        return run_pass(out, job, "render", size, src, notes, brief, out_stem, "", ("", ""),
                        mode, attempts, fidelity=fidelity)
    stem, job = find_or_new_job(out, name, inp, digest)      # again, under the lock
    if job is None:
        src = materialise_source(inp, probe, os.path.join(out, "_work"), stem)
        with Image.open(src) as im:              # upright: a rotated input became a PNG
            src_size = list(im.size)
        job = {"version": 1, "name": stem, "stem": stem, "created": now(), "input": inp,
               "input_sha256": digest, "source": rel(out, src), "source_size": src_size, "pdf_pages": probe["pages"],
               "source_note": probe.get("why") or ("PDF page 1" if probe["kind"] == "pdf"
                                                   else "the input file itself"),
               "passes": []}
        save_job(out, job)
    src = absp(out, job["source"])
    if not os.path.isfile(src):
        raise Failed("the job's source of record is missing: %s" % src)
    out_stem = free_stem(out, "%s_%s" % (stem, size))
    osrc = None
    if orig:
        osrc = materialise_source(orig, oprobe, os.path.join(out, "_work"), out_stem + "_original")
        print("   the sheet pairs the untouched original %s with the render; the model is fed "
              "the prepared copy %s" % (orig, inp), flush=True)
    title = "%s  ·  source vs %s render" % (stem, size)
    labels = ("SOURCE", "RENDER %s" % size)
    return run_pass(out, job, "render", size, src, notes, brief, out_stem, title, labels, mode,
                    attempts, fidelity=fidelity, sheet_before=osrc)


def cmd_revise(a):
    notes = read_notes(a).strip()
    if not notes:
        raise Refused("say what to change: --notes \"...\" or --notes-file F (one change per pass)")
    if len(notes) > NOTES_MAX:
        raise Refused("notes are %d characters; the limit is %d" % (len(notes), NOTES_MAX))
    mode = mode_of(a)
    out, job, idx = find_job_for_file(a.file)
    cur = gate_current(out, job, idx, mode == "live", "revise")
    size = rc.check_image_size(DRAFT_SIZE)              # revisions stay at the draft tier
    attempts = resolve_attempts(None)
    warn_camera_change(notes, "revise")
    note_tier_change(cur["size"], size, "revising")
    current_stem = os.path.splitext(os.path.basename(cur["file"]))[0]
    out_stem = next_rev_stem(out, current_stem, cur["size"], size)
    before = absp(out, cur["file"])
    if mode == "live" and not a.spend_ok:
        return estimate("revise", size, attempts, "%s (existing job, pass %d)"
                        % (job["stem"], len(job["passes"]) + 1), before, out, out_stem)
    if mode == "live":
        go_live(out)
    elif mode == "dry":
        lock_folder(out)
    if mode != "prompt":
        out_stem = next_rev_stem(out, current_stem, cur["size"], size)   # again, under the lock
    title = "%s  ·  revision  %s → %s" % (job["stem"], current_stem, out_stem)
    labels = ("BEFORE · " + current_stem, "AFTER · " + out_stem)
    return run_pass(out, job, "revise", size, before, notes, None, out_stem, title, labels,
                    mode, attempts)


def note_tier_change(from_size, to_size, action):
    if from_size != to_size:
        print("   %s a %s image at %s (policy: edits and revisions stay at %s until a single "
              "image is approved for 4K); the new file is named for the tier it is rendered at"
              % (action, from_size, to_size, to_size), flush=True)


def parse_box(s):
    try:
        v = [float(x) for x in s.split(",")]
    except ValueError:
        v = []
    if len(v) != 4 or not (0 <= v[0] < v[2] <= 1 and 0 <= v[1] < v[3] <= 1):
        raise Refused("--box must be x0,y0,x1,y1 as fractions of the frame, "
                      "0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1 (got %r)" % s)
    return v


def cmd_patch(a):
    notes = read_notes(a).strip()
    if not notes:
        raise Refused("say what to change in the box: --notes \"...\"")
    box_f = parse_box(a.box)
    mode = mode_of(a)
    out, job, idx = find_job_for_file(a.file)
    cur = gate_current(out, job, idx, mode == "live", "patch")
    size = rc.check_image_size(DRAFT_SIZE)
    attempts = resolve_attempts(None)
    warn_camera_change(notes, "patch")
    note_tier_change(cur["size"], size, "patching")
    base_path = absp(out, cur["file"])
    base = Image.open(base_path).convert("RGB")
    W, H = base.size
    x0, y0, x1, y1 = (int(round(f * s)) for f, s in zip(box_f, (W, H, W, H)))
    if min(x1 - x0, y1 - y0) < 2 * FEATHER:
        raise Refused("the patch box is %dx%d px; each side must be at least %d px on this "
                      "%dx%d image - draw a larger box" % (x1 - x0, y1 - y0, 2 * FEATHER, W, H))
    current_stem = os.path.splitext(os.path.basename(cur["file"]))[0]
    out_stem = next_rev_stem(out, current_stem, cur["size"], size)
    if mode == "live" and not a.spend_ok:
        return estimate("patch (box %s)" % a.box, size, attempts, "%s (existing job, pass %d)"
                        % (job["stem"], len(job["passes"]) + 1), base_path, out, out_stem)
    if mode == "live":
        go_live(out)
    elif mode == "dry":
        lock_folder(out)
    if mode != "prompt":
        out_stem = next_rev_stem(out, current_stem, cur["size"], size)
    work = os.path.join(out, "_work")
    if mode == "prompt":
        work = os.path.join(work, "prompt-only")
    os.makedirs(work, exist_ok=True)
    crop = base.crop((x0, y0, x1, y1))
    cpath = os.path.join(work, "%s_patch_crop.png" % out_stem)
    crop.save(cpath)
    feed = os.path.join(work, out_stem + "_padded.jpg")
    ratio, grew, box = pad_to(shrink_for_feed(crop), feed)
    prompt = build_patch_prompt(notes, grew)
    prompt_file = os.path.join(work, out_stem + "_prompt.txt")
    write_text(prompt_file, prompt)
    print("===== %s | patch | %s | box px %s | %s canvas, pad %s | %s =====" % (
        job["stem"], size, (x0, y0, x1, y1), ratio, grew or "none",
        {"live": "LIVE - billed", "dry": "DRY RUN - no API call", "prompt": "PROMPT ONLY"}[mode]),
        flush=True)
    if mode == "prompt":
        return print_prompt(prompt, prompt_file, feed)

    t0 = time.time()
    title = "%s  ·  patch  %s → %s" % (job["stem"], current_stem, out_stem)
    labels = ("BEFORE · " + current_stem, "AFTER · " + out_stem)
    ps = new_pass(out, "patch", size, base_path, notes, None, mode, out_stem, title, labels,
                  MODEL)
    ps.update(ratio=ratio, grew=grew, box=list(box), feed=rel(out, feed),
              prompt_file=rel(out, prompt_file), patch_box=box_f, patch_px=[x0, y0, x1, y1])
    job["passes"].append(ps)
    save_job(out, job)
    out_base = os.path.join(out, "_work", out_stem + "_raw")
    raw = None
    try:
        raw = call_model(out, job, ps, feed, prompt, out_base, size, ratio, False,
                         base_path, attempts, mode, notes)
        if not raw:
            raise RuntimeError("the model returned no image (%s)" % attempts_summary(ps))
        rc.forget(raw)                                   # patches are not sheet rows
        ps["raw"] = rel(out, raw)
        save_job(out, job)
        with Image.open(raw) as im:
            rw, rh = im.size
        drift = abs((rw / rh) / RATIOS[ratio] - 1)
        if drift > cs.ASPECT_TOL:
            fail_pass(out, job, ps, t0,
                      "the model re-framed the patch crop (%.3f:1 for a %s request), so it "
                      "cannot be pasted back - nothing was changed. Fix the box or the note and "
                      "patch again" % (rw / rh, ratio), raw)
            return EXIT_ERROR
        epath = os.path.join(out, "_work", "%s_patch_edit.png" % out_stem)
        crop_back(raw, box, epath, crop.width / float(crop.height))
        edit = Image.open(epath).convert("RGB").resize(crop.size, Image.LANCZOS)
        m = feather_mask(crop.width, crop.height, x0 > 0, x1 < W, y0 > 0, y1 < H)
        comp = base.copy()
        comp.paste(edit, (x0, y0), m)
        finish_pass(out, job, ps, raw, t0, final_override=comp)
    except rc.SpendCapReached as e:
        fail_pass(out, job, ps, t0, "SpendCapReached: %s" % e)
        return EXIT_ERROR
    except KeyboardInterrupt:
        fail_pass(out, job, ps, t0, "interrupted - a live attempt may already have been billed")
        return EXIT_ERROR
    except Exception as e:
        fail_pass(out, job, ps, t0, "%s: %s" % (type(e).__name__, e), raw)
        return EXIT_ERROR
    return report(out, ps)


def upscale_target(path, mode, force):
    """The approved pass a 4K may start from, or Refused: the current pass of its job, with
    its sheet, no warning, the source's shape, and no earlier 4K unless forced."""
    out, job, idx = find_job_for_file(path)
    cur = gate_current(out, job, idx, mode == "live", "upscale")
    adopt_sheet(out, job, cur)                          # one built by hand at the expected path
    if not cur.get("sheet") or not os.path.isfile(absp(out, cur["sheet"])):
        raise Refused("%s has no comparison sheet, so it has not been cross-verified - run "
                      "'render.py sheet' on it, review the sheet with the user, then upscale"
                      % os.path.basename(cur["file"]))
    already = [p for p in job["passes"] if p["kind"] == "4k" and p["status"] == "done"
               and p["before"] == cur["file"] and bool(p.get("dry_run")) == (mode == "dry")]
    if already and not force and mode != "prompt":
        raise Refused("this exact image already has a %s4K render (%s, pass %d). A second 4K "
                      "is refused unless the user asks for it and you pass --force."
                      % ("dry-run " if mode == "dry" else "", os.path.basename(already[-1]["file"]),
                         job["passes"].index(already[-1]) + 1))
    return out, job, cur


def cmd_upscale(a):
    mode = mode_of(a)
    if not a.confirmed and mode != "prompt":
        print(REMINDER, flush=True)
        # What approval would cost, so the question to the user can quote it. Nothing is
        # read or sent; the exit code stays 2.
        try:
            out, job, cur = upscale_target(a.file, "live", a.force)
            print("\nIf the user approves THIS file by name for 4K (%s):\n%s\nthen re-run with "
                  "--confirmed." % (absp(out, cur["file"]),
                                    "\n".join(estimate_lines("4K", resolve_attempts(None)))),
                  flush=True)
        except (Refused, Failed) as e:
            print("\nThis file cannot be approved for 4K as it stands: %s" % e, flush=True)
        return EXIT_REFUSED
    out, job, cur = upscale_target(a.file, mode, a.force)
    size, confirmed = "4K", True
    attempts = resolve_attempts(None)
    current_stem = os.path.splitext(os.path.basename(cur["file"]))[0]
    before = absp(out, cur["file"])
    if mode == "live":
        usd = attempts * price(size)
        print("4K pass of the approved image %s: 1 image, 4K, up to %d attempt(s), max USD %.3f "
              "(INR %.0f) at list price, model %s" % (os.path.basename(before), attempts, usd,
                                                      usd * INR_PER_USD, MODEL), flush=True)
        go_live(out)
    elif mode == "dry":
        lock_folder(out)
    out_stem = free_stem(out, current_stem + "_4K")
    tier = cur.get("size") or "1K"                # the local app's labels; the real tier of a 2K pass
    title = "%s  ·  4K upscale: approved %s vs 4K" % (job["stem"], tier)
    labels = ("APPROVED %s · %s" % (tier, current_stem), "4K · " + out_stem)
    return run_pass(out, job, "4k", size, before, upscale_notes(job, cur), None, out_stem, title,
                    labels, mode, attempts, confirmed=confirmed)


def cmd_sheet(a):
    out, job, idx = find_job_for_file(a.file)
    ps = job["passes"][idx]
    if ps["status"] != "done" or not ps.get("out_stem"):
        raise Refused("that pass has no delivered file to build a sheet from")
    lock_folder(out)
    before, final = absp(out, ps.get("sheet_before") or ps["before"]), absp(out, ps["file"])
    written = rc.write_comparison_sheet(out=sheet_path_for(out, ps), title=ps["title"],
                                        before_label=ps["labels"][0],
                                        after_label=ps["labels"][1],
                                        pairs=[(ps["out_stem"], before, final)])
    if not written:
        ps["error"] = ("the comparison sheet could not be written - the console says why; "
                       "it cannot be approved for 4K until it exists")
        save_job(out, job)
        raise Failed(ps["error"])
    ps["sheet"], ps["error"] = rel(out, written[0]), None
    save_job(out, job)
    print("sheet   : %s" % written[0])
    return EXIT_OK


def find_outs(d):
    d = os.path.abspath(d)
    if os.path.basename(d) == "_jobs":
        return [os.path.dirname(d)]
    if os.path.isdir(jobs_dir(d)):
        return [d]
    outs = sorted({os.path.dirname(os.path.dirname(p)) for p in
                   glob.glob(os.path.join(glob.escape(d), "*", "_jobs", "*.json"))
                   + glob.glob(os.path.join(glob.escape(d), "*", "*", "_jobs", "*.json"))})
    return outs


def cmd_status(a):
    outs = find_outs(a.dir or os.getcwd())
    if not outs:
        print("no render jobs under %s" % os.path.abspath(a.dir or os.getcwd()))
        return EXIT_OK
    n_ok, attempts, usd, errors = 0, 0, 0.0, 0
    for out in outs:
        print("\n%s" % out)
        for j in sorted(all_jobs(out), key=lambda j: j.get("created", "")):
            sw, sh = j["source_size"]
            print("  job '%s'   source %s   %dx%d (%.3f:1)%s" % (
                j["stem"], j["source"], sw, sh, sw / sh,
                "   PDF, %d page(s)" % j["pdf_pages"] if j.get("pdf_pages") else ""))
            cur_live, cur_any = current_of(j, True), current_of(j, False)
            for i, p in enumerate(j["passes"], 1):
                tag = []
                if p is cur_live:
                    tag.append("CURRENT")
                elif p is cur_any:
                    tag.append("current (dry run)")
                if p.get("dry_run"):
                    cost = "dry run, no cost"
                else:
                    cost = "%d billed attempt(s)  USD %.3f  INR %.1f" % (
                        p.get("attempts") or 0, p.get("cost_usd") or 0.0, p.get("cost_inr") or 0.0)
                    extra = [s for s in (
                        "%d HTTP error(s), not billed" % p["http_errors"] if p.get("http_errors") else "",
                        "%d never sent" % p["not_sent"] if p.get("not_sent") else "") if s]
                    if extra:
                        cost += "  (+ %s)" % ", ".join(extra)
                    attempts += p.get("attempts") or 0
                    usd += p.get("cost_usd") or 0.0
                    errors += (p.get("http_errors") or 0)
                    if p["status"] == "done":
                        n_ok += 1
                status = p["status"]
                if status == "running":
                    status = "running/interrupted"
                print("    #%d %-6s %-3s %-20s %s  sheet:%s  %s%s" % (
                    i, p["kind"], p["size"], status,
                    os.path.basename(p["file"]) if p.get("file") else "-",
                    "yes" if p.get("sheet") else "NO", cost,
                    ("  [" + ", ".join(tag) + "]") if tag else ""))
                if p.get("warning"):
                    print("         WARNING: %s" % p["warning"])
                if p.get("error"):
                    print("         error: %s" % p["error"].splitlines()[0])
    print("\nlive totals: %d delivered pass(es), %d billed attempt(s), USD %.3f, INR %.0f "
          "(list-price estimate; INR at %.1f per USD)%s" % (
              n_ok, attempts, usd, usd * INR_PER_USD, INR_PER_USD,
              "; %d HTTP error response(s) booked as not billed" % errors if errors else ""))
    print("The real bill is in AI Studio (aistudio.google.com/spend).")
    return EXIT_OK


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def cmd_check(a):
    import PIL
    ok = True
    py = sys.version_info
    print("python    : %s %s" % (sys.version.split()[0],
                                 "ok" if py >= (3, 9) else "TOO OLD - need 3.9+"))
    ok &= py >= (3, 9)
    pv = tuple(int(x) for x in re.findall(r"\d+", PIL.__version__)[:2])
    print("Pillow    : %s %s" % (PIL.__version__, "ok" if pv >= (10, 1) else
                                 "old - 10.1+ recommended (pip install -U pillow)"))
    try:
        import fitz
        print("PyMuPDF   : %s (PDF input enabled)" % getattr(fitz, "VersionBind", "installed"))
    except ImportError:
        print("PyMuPDF   : not installed - PDF input disabled (pip install pymupdf)")
    print("sheet font: %s" % FONT_STATUS)
    print("model     : %r%s" % (MODEL, "  (from env MODEL)" if os.environ.get("MODEL") else ""))
    if MODEL_OK:
        print("endpoint  : %s/v1beta/models/%s:generateContent" % (api_base(), MODEL))
    else:
        print("!! MODEL  : %s" % MODEL_PROBLEM)
        ok = False
    print("tiers     : drafts %s, attempts %d per pass (each billed), 4K only via "
          "'upscale --confirmed'" % (DRAFT_SIZE, ATTEMPTS))
    if ATTEMPTS_NOTE:
        print("!! %s" % ATTEMPTS_NOTE)
        ok = False
    if ATTEMPTS > MAX_ATTEMPTS:
        print("!! ATTEMPTS=%d exceeds the cap of %d - render, revise, patch and upscale will "
              "refuse. Fix the prompt instead of raising the retry count." % (ATTEMPTS, MAX_ATTEMPTS))
        ok = False
    try:
        rc.check_image_size(DRAFT_SIZE)
    except Exception as e:
        print("!! IMAGE_SIZE: %s" % str(e).splitlines()[0])
        ok = False
    label = load_key()
    if label:
        redact_key_in_output()
        print("key       : found - %s (value not shown)" % label)
    else:
        print("key       : NOT FOUND")
        print(MISSING_KEY % (os.path.join(os.getcwd(), ".env"), os.path.join(SKILL_DIR, ".env")))
    if a.online:
        if not label:
            print("!! --online needs a key")
            return EXIT_ERROR
        if not MODEL_OK:
            return EXIT_ERROR
        url = "%s/v1beta/models/%s" % (api_base(), urllib.parse.quote(MODEL))
        print("online    : GET %s (models.get metadata - free, never billed)" % url)
        req = urllib.request.Request(url, headers={"x-goog-api-key": os.environ["GOOGLE_API_KEY"]})
        try:
            with urllib.request.build_opener(_NoRedirect).open(req, timeout=30) as r:
                data = json.loads(r.read(2_000_000))
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                msg = json.loads(e.read(65536)).get("error", {}).get("message", "")
            except Exception:
                pass
            key = os.environ.get("GOOGLE_API_KEY", "")
            if key:
                msg = msg.replace(key, "***")
            print("!! HTTP %d %s" % (e.code, msg[:300]))
            print("   401: the key is invalid or expired. 403: the key lacks permission (for example "
                  "it is not restricted to the Gemini API). 404: this model id is not served to the key.")
            return EXIT_ERROR
        except Exception as e:
            print("!! could not reach %s: %s" % (api_base(), type(e).__name__))
            return EXIT_ERROR
        methods = data.get("supportedGenerationMethods") or []
        print("            name %s | %s | version %s" % (data.get("name"), data.get("displayName"),
                                                         data.get("version")))
        print("            generateContent supported: %s" % ("yes" if "generateContent" in methods
                                                              else "NO"))
        ok &= "generateContent" in methods
        print("            (this free call does not prove billing is on: without billing the first "
              "render fails with HTTP 400 FAILED_PRECONDITION or a 429 naming a free-tier limit of 0)")
    return EXIT_OK if ok else EXIT_ERROR


# ======================================================================= main
def build_parser():
    p = argparse.ArgumentParser(prog="render.py", description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="environment, font, key source and model")
    c.add_argument("--online", action="store_true",
                   help="also make the free models.get metadata call (never billed)")

    def gate_flags(q, spend=True):
        g = q.add_mutually_exclusive_group()
        g.add_argument("--dry-run", action="store_true",
                       help="no API call: a stamped stand-in goes through the real crop/sheet path")
        g.add_argument("--prompt-only", action="store_true",
                       help="build the feed and print the exact prompt; record nothing")
        if spend:
            g.add_argument("--spend-ok", action="store_true",
                           help="the user has said yes to the estimate: make the billed call")

    def notes_flags(q, what):
        g = q.add_mutually_exclusive_group()
        g.add_argument("--notes", help=what)
        g.add_argument("--notes-file", help="read the notes from a UTF-8 text file instead")

    r = sub.add_parser("render", help="first pass from a drawing, at 1K")
    r.add_argument("input")
    r.add_argument("--name", help="view name (default: the input file name)")
    notes_flags(r, "free-text notes (or use the four field flags, not both)")
    r.add_argument("--original", help="the untouched export, when the input is a prepared copy "
                   "of it (lines cleaned, labels erased): the sheet pairs this original")
    r.add_argument("--materials")
    r.add_argument("--lighting")
    r.add_argument("--environment")
    r.add_argument("--other")
    r.add_argument("--brief", help="brief JSON {elements, finishes, cautions} written for this view")
    r.add_argument("--no-terracotta-example", action="store_true",
                   help="drop FIDELITY_PROMPT's terracotta example (roofs are not terracotta)")
    r.add_argument("--out", help="output folder (default: sibling '03 Output')")
    r.add_argument("--size", type=str.upper, choices=("1K", "2K"),
                   help="draft tier (default 1K; 4K is refused here)")
    r.add_argument("--attempts", type=int, help="attempts per pass (default 2, max 3)")
    gate_flags(r)

    v = sub.add_parser("revise", help="one change on the current render, at 1K")
    v.add_argument("file")
    notes_flags(v, "the one change to make")
    gate_flags(v)

    t = sub.add_parser("patch", help="local edit of one region of the current render, at 1K")
    t.add_argument("file")
    t.add_argument("--box", required=True, help="x0,y0,x1,y1 as fractions of the frame")
    notes_flags(t, "the change to make inside the box")
    gate_flags(t)

    u = sub.add_parser("upscale", help="4K re-render of ONE approved image")
    u.add_argument("file")
    u.add_argument("--confirmed", action="store_true",
                   help="the user approved THIS image, by name, for 4K")
    u.add_argument("--force", action="store_true", help="allow a second 4K of the same image")
    gate_flags(u, spend=False)

    s = sub.add_parser("sheet", help="rebuild a pass's comparison sheet (local, free)")
    s.add_argument("file")

    st = sub.add_parser("status", help="jobs, passes, warnings and list-price cost")
    st.add_argument("dir", nargs="?")
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    rc.disable_comparison_sheet()       # every pass writes its own sheet explicitly
    handlers = {"check": cmd_check, "render": cmd_render, "revise": cmd_revise,
                "patch": cmd_patch, "upscale": cmd_upscale, "sheet": cmd_sheet,
                "status": cmd_status}
    if not MODEL_OK and a.cmd in ("render", "revise", "patch", "upscale"):
        print("!! %s Nothing was sent." % MODEL_PROBLEM, flush=True)
        return EXIT_ERROR
    try:
        return handlers[a.cmd](a)
    except Refused as e:
        print("REFUSED: %s" % e, flush=True)
        return EXIT_REFUSED
    except rc.FourKNotConfirmedError as e:
        print(str(e), flush=True)
        return EXIT_REFUSED
    except ValueError as e:
        if "image_size" in str(e):
            print("REFUSED: %s" % e, flush=True)
            return EXIT_REFUSED
        raise
    except Failed as e:
        print(str(e) if str(e).startswith("!!") else "!! %s" % e, flush=True)
        return EXIT_ERROR
    except OSError as e:                # a file that cannot be read or written: plain message
        print("!! %s: %s" % (type(e).__name__, e), flush=True)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
