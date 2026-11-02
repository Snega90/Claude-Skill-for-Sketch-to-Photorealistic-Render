#!/usr/bin/env python3
"""Before/after comparison sheets - MANDATORY after every render.

Standing requirement (user, 31 Aug 2026):

    In all the future renders, after every render I want a comparison sheet to
    cross verify.

So every render job - first pass, revision, fix, variant, 4K upscale - ships a
sheet pairing each source view with what came back, side by side, so geometry,
framing and content can be cross-checked against the input before anything is
delivered. A render without its sheet is not finished.

This is the ONE shared implementation for the whole tree. The per-estate
comparison_sheet.py files are thin shims that call into this one, and
_render_common.generate() writes a sheet automatically at the end of every run,
so in practice nobody has to remember any of the above.

CLI - run it from anywhere:

    python comparison_sheet.py --root "project 16"
    python comparison_sheet.py                       # cwd / script dir as root
    python comparison_sheet.py --filter "Villa 02"   # subset by view name
    python comparison_sheet.py --before "03 Output/Archive v5" --after "03 Output" \
        --title "Villa 02 - timber removed" --before-label "v5" --after-label "v6" \
        --out "03 Output/_Before After Villa 02.jpg"
    python comparison_sheet.py --pair "View 01|02 Input/a.png|03 Output/a.png"

Import API - used by _render_common and by any render script:

    import comparison_sheet as cs
    cs.sheet([(label, before_path, after_path), ...], out="...", title="...")

Pillow is the only dependency. Century Gothic per the standing font rule.
"""
import argparse, glob, os, re, sys

# ------------------------------------------------------------------ styling
# On Windows the fonts are found in C:\Windows\Fonts. On a server, set COMPARISON_FONT_DIR to a folder that holds
# GOTHIC.TTF and GOTHICB.TTF (exact names).
_FONT_DIR = os.environ.get("COMPARISON_FONT_DIR", "").strip()
GOTHIC = os.path.join(_FONT_DIR, "GOTHIC.TTF") if _FONT_DIR else r"C:\Windows\Fonts\GOTHIC.TTF"
GOTHICB = os.path.join(_FONT_DIR, "GOTHICB.TTF") if _FONT_DIR else r"C:\Windows\Fonts\GOTHICB.TTF"

TW = 940          # tile width, px (default; --tile-width overrides)
PAD = 16
LBL = 32          # label strip under each row
HEAD = 92         # sheet header
BG = (250, 249, 247)
INK = (28, 28, 30)
SUB = (110, 110, 116)
WARN = (176, 74, 26)

PER_SHEET = 8     # rows per sheet before it pages; 0 disables paging
ASPECT_TOL = 0.02  # tolerated source-to-render aspect drift before a row is flagged
IMG_EXT = ("*.png", "*.jpg", "*.jpeg", "*.webp")

# Suffixes a render pipeline bolts onto an output name. Stripped when matching a
# render back to its source, so "Villa 02 (3)_rev02_1K.png" still finds
# "Villa 02 (3) - SketchUp Style.png", and "SITE MASTERPLAN 01_render_v4.png"
# still finds "SITE MASTERPLAN 01.jpg". Only tokens that follow a separator are
# stripped, so a real word in a view name ("Villa Type 01 New") survives.
STRIP = re.compile(
    r"(\s*[-_]\s*SketchUp Style"
    r"|[-_](?:1K|2K|4K|8K)"
    r"|[-_](?:raw|fresh|final|render|renders|rendered|photoreal|edit|edited"
    r"|upscale|upscaled|clean)"
    r"|[-_](?:rev|ver|var|v|pass|opt|option)\s*\d*"
    r")+$", re.I)

_warned_font = False


def font(path, size):
    """Century Gothic, or the closest thing this box has - and say so once."""
    global _warned_font
    from PIL import ImageFont
    for p in (path, GOTHIC, r"C:\Windows\Fonts\FUTURA.TTF"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    if not _warned_font:
        print("!! Century Gothic not available - falling back to Pillow's default font. "
              "Install Century Gothic for correctly styled sheets.")
        _warned_font = True
    try:
        return ImageFont.load_default(size)      # Pillow >= 10.1 honours the size
    except TypeError:
        return ImageFont.load_default()


# ------------------------------------------------------------------ matching
def display(path):
    """Human-readable view name: suffixes stripped, original case kept."""
    b = os.path.splitext(os.path.basename(path))[0]
    return STRIP.sub("", b).strip(" -_") or b


def key(path):
    return display(path).lower()


def _images(d):
    out = []
    for pat in IMG_EXT:
        out += glob.glob(os.path.join(d, pat))
    # "_" prefixes the sheets themselves and other non-view artefacts.
    return [f for f in out if not os.path.basename(f).startswith("_")]


def find_dirs(root):
    """Guess (before, after) from an estate folder's numbered subdirectories.

    Handles every layout in this tree: "02 Input"/"03 Output" (projects 14 and 16),
    "01 Input"/"02 Output" (project 15), and plain "Input"/"Output".
    """
    subs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]

    def pick(word):
        hits = sorted(d for d in subs if word in d.lower())
        return os.path.join(root, hits[0]) if hits else None

    return pick("input"), pick("output")


def collect(before_dir, after_dir, filt=""):
    """Pair every source view with its render, by name, ignoring suffix and case."""
    after = {}
    for f in _images(after_dir):
        after.setdefault(key(f), f)
    pairs = []
    for f in sorted(_images(before_dir)):
        k = key(f)
        if k in after and (not filt or filt.lower() in k):
            pairs.append((display(f), f, after[k]))
    return pairs


# -------------------------------------------------------------------- render
def fit(path, w):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    return im.resize((w, max(1, round(im.size[1] * w / im.size[0]))), Image.LANCZOS)


def _aspect_note(before, after):
    """Flag a row whose render came back in a different shape from its source.

    A changed aspect ratio means the frame was re-cropped or re-framed, which the
    standing policy forbids - so it is called out on the sheet rather than left
    for someone to notice.

    The 2% tolerance is deliberate: pad-and-crop-back pipelines land about 1% off
    on integer rounding alone, which is not a framing change. A genuine reframe -
    e.g. delivering 21:9 over a 2.14 export - is 10% out and still trips.
    """
    from PIL import Image
    try:
        with Image.open(before) as b, Image.open(after) as a:
            rb = b.size[0] / b.size[1]
            ra = a.size[0] / a.size[1]
    except Exception:
        return ""
    if rb and abs(ra / rb - 1) > ASPECT_TOL:
        return "  !! aspect %.3f -> %.3f  (framing changed)" % (rb, ra)
    return ""


def _page(rows, title, subtitle, before_label, after_label, out, tw=TW):
    from PIL import Image, ImageDraw
    f_lab = font(GOTHIC, 20)
    f_tag = font(GOTHICB, 20)
    f_ttl = font(GOTHICB, 34)
    f_sub = font(GOTHIC, 19)

    W = 2 * tw + 3 * PAD
    H = HEAD + sum(r[3] + LBL + PAD for r in rows) + PAD
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((PAD + 4, 24), title, font=f_ttl, fill=INK)
    d.text((PAD + 4, 62), subtitle, font=f_sub, fill=SUB)

    y = HEAD
    for name, ib, ia, h, note in rows:
        sheet.paste(ib, (PAD, y))
        sheet.paste(ia, (PAD * 2 + tw, y))
        left_text = "%s   \u00b7  %s" % (name, before_label)
        right_text = "%s   \u00b7  %s" % (name, after_label)
        d.text((PAD + 4, y + h + 6), left_text, font=f_lab, fill=SUB)
        d.text((PAD * 2 + tw + 4, y + h + 6), right_text, font=f_tag, fill=INK)
        if note:
            try:
                dx = f_tag.getlength(right_text)
            except AttributeError:
                dx = d.textlength(right_text, font=f_tag)
            d.text((PAD * 2 + tw + 4 + dx, y + h + 6), note, font=f_lab, fill=WARN)
        y += h + LBL + PAD

    outdir = os.path.dirname(os.path.abspath(out))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    sheet.save(out, quality=88)
    print("   %-58s %dx%d  %d KB"
          % (os.path.basename(out), sheet.size[0], sheet.size[1],
             os.path.getsize(out) // 1024))
    return out


def sheet(pairs, out, title="Before / After", before_label="SOURCE",
          after_label="RENDER", per_sheet=PER_SHEET, tile_width=None):
    """Write one comparison sheet per `per_sheet` rows. Returns the paths written."""
    if not pairs:
        raise ValueError("no pairs to compare")
    tw = int(tile_width or TW)
    rows = []
    for name, b, a in pairs:
        ib, ia = fit(b, tw), fit(a, tw)
        rows.append((name, ib, ia, max(ib.size[1], ia.size[1]), _aspect_note(b, a)))

    n = per_sheet if per_sheet and per_sheet > 0 else len(rows)
    pages = [rows[i:i + n] for i in range(0, len(rows), n)]
    stem, ext = os.path.splitext(out)
    ext = ext or ".jpg"
    flagged = sum(1 for r in rows if r[4])

    print("comparison sheet: %d pair%s%s"
          % (len(rows), "" if len(rows) == 1 else "s",
             ", %d with changed framing" % flagged if flagged else ""))
    written = []
    for i, page in enumerate(pages, 1):
        path = out if len(pages) == 1 else "%s (%d of %d)%s" % (stem, i, len(pages), ext)
        sub = "left: %s      right: %s      %d pair%s" % (
            before_label, after_label, len(page), "" if len(page) == 1 else "s")
        if len(pages) > 1:
            sub += "      sheet %d of %d" % (i, len(pages))
        written.append(_page(page, title, sub, before_label, after_label, path, tw))
    return written


def from_root(root, filt="", title=None, out=None, before=None, after=None,
              before_label="SOURCE", after_label="RENDER", per_sheet=PER_SHEET):
    """Scan an estate folder and build its sheet. Returns the paths written."""
    root = os.path.abspath(root)
    guess_b, guess_a = find_dirs(root)
    before = before or guess_b
    after = after or guess_a
    if not before or not after:
        raise SystemExit("could not find input/output folders under %s - pass "
                         "--before and --after" % root)
    pairs = collect(before, after, filt)
    if not pairs:
        raise SystemExit("no matching pairs between %s and %s%s"
                         % (before, after, " for filter %r" % filt if filt else ""))
    name = os.path.basename(root)
    title = title or ("%s  \u00b7  Before / After%s"
                      % (name, "  \u00b7  " + filt if filt else ""))
    out = out or os.path.join(after, "_Before After%s.jpg" % (" " + filt if filt else ""))
    return sheet(pairs, out, title, before_label, after_label, per_sheet)


# ----------------------------------------------------------------------- CLI
def main(argv=None, here=None):
    here = here or os.getcwd()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--root", default=here,
                   help="estate folder holding the input/output subfolders")
    p.add_argument("--before", default=None, help="override the source folder")
    p.add_argument("--after", default=None, help="override the render folder")
    p.add_argument("--filter", default="", help="only views whose name contains this")
    p.add_argument("--title", default=None)
    p.add_argument("--before-label", default="SOURCE")
    p.add_argument("--after-label", default="RENDER")
    p.add_argument("--out", default=None)
    p.add_argument("--per-sheet", type=int, default=PER_SHEET,
                   help="rows per sheet before it pages; 0 for one tall sheet")
    p.add_argument("--tile-width", type=int, default=TW,
                   help="width of each image tile in px (default %d); raise it for "
                        "a sheet you intend to zoom into" % TW)
    p.add_argument("--pair", action="append", default=[],
                   help="explicit row as 'label|before path|after path'; repeatable. "
                        "Overrides the folder scan when given.")
    a = p.parse_args(argv)

    root = os.path.abspath(os.path.join(here, a.root))

    def rel(q):
        return q if os.path.isabs(q) else os.path.join(root, q)

    if a.pair:
        pairs = []
        for spec in a.pair:
            label, b, af = [s.strip() for s in spec.split("|")]
            pairs.append((label, rel(b), rel(af)))
        sheet(pairs, rel(a.out or "_Before After.jpg"),
              a.title or "Before / After", a.before_label, a.after_label, a.per_sheet,
              a.tile_width)
    else:
        from_root(root, a.filter, a.title,
                  rel(a.out) if a.out else None,
                  rel(a.before) if a.before else None,
                  rel(a.after) if a.after else None,
                  a.before_label, a.after_label, a.per_sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
