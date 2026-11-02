#!/usr/bin/env python3
"""Shared render helper for this project - 1K FIRST IS THE DEFAULT PATH.

Import this instead of hand-rolling another render script, so that every future
render obeys the standing policy below without anyone having to remember it.

THE USER'S STANDING RENDER POLICY (verbatim):

  Task: Render the input image in 1K quality first to reduce cost.
  - Maintain 100% accurate geometry, scale, and ratio.
  - No hallucination, no element addition/removal unless explicitly instructed.
  - Replace materials with real finishes (e.g., terracotta roofs, realistic
    trees, pools, landscapes).
  - Output must look like high-end DSLR architectural photography.
  - All edits and revisions should remain in 1K quality until confirmed.

  Once approved, upscale the same image to 4K quality:
  - Deliver sharp, detailed accuracy with no blur or smudge.
  - Every element must appear real and photorealistic when zoomed in.
  - Preserve exact geometry and detail fidelity from the reference image.

  Final rule: Always render edits in 1K first, then enhance to 4K only after
  explicit confirmation.

HOW THAT POLICY IS ENFORCED HERE:
  - generate() defaults to image_size="1K". Every draft, edit and revision
    therefore costs 1K money unless someone deliberately says otherwise.
  - generate() REFUSES image_size="4K" unless confirmed_4k=True is passed in
    the same call. The 4K path cannot be reached by a typo, by a merely truthy
    value, or by an environment variable - only by code that states the
    confirmation outright.
  - The 4K pass is meant to be driven by upscale_to_4k.py, which additionally
    requires an explicit --confirmed flag on the command line.
  - After every render generate() prints the delivered pixel size and warns if
    it is not the tier that was requested, so an ignored size parameter cannot
    quietly turn a 1K batch into 4K billing.

THE SECOND STANDING REQUIREMENT - A COMPARISON SHEET AFTER EVERY RENDER
(user, 31 Aug 2026):

    In all the future renders, after every render I want a comparison sheet to
    cross verify.

Every render job - first pass, revision, fix, variant, 4K upscale - has to ship
a side-by-side sheet of source against result, so geometry, framing and content
can be cross-checked before anything is delivered. That is automatic here:
generate() records each source/result pair, and the sheet is written when the
script finishes, without the script having to ask. Scripts that post-process a
render (pad, crop, composite) should pass compare_src= or call record() so the
sheet pairs the true original against the delivered file.

  - set COMPARISON_SHEET=0 in the environment to skip it for a one-off run
  - build one by hand any time with comparison_sheet.py (see its --help)

Standard library only for the render path: plain urllib, no third-party
dependencies. The comparison sheet needs Pillow, which is imported lazily and
only when a sheet is actually written - a missing Pillow warns, it never costs
you a render. Importing this module has no side effects: it makes no network
calls, creates no directories and reads no API key until generate() is called.
"""
import atexit, base64, json, os, struct, sys, time, urllib.request, urllib.error

# --------------------------------------------------------------- constants
DEFAULT_IMAGE_SIZE = "1K"                      # policy: 1K until confirmed

# Model id. "gemini-3-pro-image" is the GA id for Nano Banana Pro (released 28 May
# 2026). The earlier "gemini-3-pro-image-preview" id was deprecated on 20 Nov 2025 with
# shutdown announced for 25 Jun 2026 and is no longer on the models page; it still
# answered models.get on 3 Oct 2026 (same display name and version as the GA id) but can
# stop being served without further notice. Checked 3 Oct 2026 against
# ai.google.dev/gemini-api/docs/deprecations and the free models.get endpoint.
MODEL   = "gemini-3-pro-image"
URL     = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
MIME    = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
           "webp": "image/webp"}
SIZES   = ("1K", "2K", "4K")

# REQUEST SHAPE, verified 3 Oct 2026 against the REST reference
# (ai.google.dev/api/generate-content) and the free countTokens endpoint, which parses
# the same generationConfig as generateContent:
#   - generationConfig.imageConfig.imageSize ("1K" | "2K" | "4K", default 1K) is a live,
#     undeprecated field on the legacy generateContent endpoint. Unknown field names are
#     rejected with HTTP 400, so the size is NOT silently dropped. That is the shape
#     generate() sends.
#   - The same endpoint also accepts generationConfig.responseFormat.image.imageSize, but
#     only as enum names (IMAGE_SIZE_ONE_K ...); the "1K" spelling is rejected there.
#   - The Interactions API (/v1beta/interactions) uses response_format{type:"image",
#     image_size:"1K"}. The May 2026 "image_config moves to response_format" breaking
#     change applies to that endpoint only, not to generateContent.
# Do not mix the three shapes. If Google ever drops imageConfig, the delivered-size check
# in generate() flags the mismatch on the first render.

# Upper bound of the long side, in pixels, for each tier. 1K comes back at ~1024-1536 on
# the long side depending on aspect, 2K ~2048-3072, 4K ~4096-6144. Used only to warn.
_TIER_LONG_SIDE = (("1K", 1800), ("2K", 3600), ("4K", float("inf")))

# List-price guidance used by the 4K CLI when it warns before spending.
USD_PER_4K_IMAGE = 0.24
INR_PER_4K_IMAGE = 21

# ---------------------------------------------------------- the fidelity brief
FIDELITY_PROMPT = (
    "Re-render this architectural image as a real photograph while keeping the design "
    "identical.\n\n"
    "GEOMETRY - NON-NEGOTIABLE:\n"
    "- Maintain 100% accurate geometry, scale and ratio. Same camera position, lens "
    "angle, horizon and framing: no zoom, pan or crop.\n"
    "- Every wall, roof plane, overhang, column, floor level, step, terrace, railing, "
    "pergola, window and door opening stays in exactly the same place, at exactly the "
    "same proportion, with the same mullion and glazing grid.\n"
    "- The site stays as drawn: pool position, shape and size; paving patterns; "
    "driveways; boundary walls; planter bed layout; furniture positions.\n\n"
    "NO HALLUCINATION:\n"
    "- Do not invent, add, remove, move, resize or redesign any element unless you have "
    "been explicitly instructed to. No extra storeys, wings, openings, chimneys, "
    "canopies, steps, plants or furniture. Nothing may quietly disappear either.\n\n"
    "MATERIALS BECOME REAL FINISHES:\n"
    "- Replace placeholder materials with real photographed finishes: terracotta roof "
    "tiles with true clay colour variation and weathering; real trees, shrubs and lawns "
    "with individual leaves, real bark, natural asymmetry and see-through canopies; real "
    "pool water with ripples, refraction and caustics; real landscape and terrain with "
    "atmospheric depth; lime plaster with subtle tonal variation; timber with true grain; "
    "glass with real reflections of sky and foliage; stone with fine natural texture.\n\n"
    "OUTPUT LOOK:\n"
    "- The result must look like high-end DSLR architectural photography - an actual "
    "frame shot on a full-frame camera with a professional lens: true perspective, "
    "physically correct exposure, sharp focus, natural lighting, soft highlight roll-off, "
    "open readable shadows, accurate white balance, faint natural sensor grain.\n\n"
    "ABSOLUTELY FORBIDDEN: any CGI / 3D-render / SketchUp / video-game look, "
    "illustration, cartoon, outlines, flat colour fills, plastic or over-smooth surfaces, "
    "repeating texture tiles, oversaturation, HDR halos. No people, no vehicles, no text, "
    "no logos, no watermarks, no signatures. Output ONE photograph only, matching the "
    "input framing."
)

# ------------------------------------------------ the 4K (post-approval) brief
UPSCALE_PROMPT = (
    "4K QUALITY PASS on an already-approved image.\n"
    "- Deliver sharp, detailed accuracy with no blur, no smudge, no soft mush and no "
    "painterly smearing anywhere in the frame.\n"
    "- Every element must appear real and photorealistic when zoomed in: roof tiles read "
    "as individual tiles, foliage resolves into individual leaves, stone and plaster show "
    "true micro-texture, water shows real ripple and caustic detail, joinery and railings "
    "keep crisp straight edges.\n"
    "- Preserve exact geometry and detail fidelity from the reference image: identical "
    "composition, framing, perspective, proportions, materials, colours, lighting and "
    "shadows. This is a resolution and sharpness pass only.\n"
    "- Add nothing and remove nothing. Do not restyle, recolour, relight or redesign any "
    "part of the approved image."
)


class FourKNotConfirmedError(RuntimeError):
    """Raised when a 4K render is requested without explicit user confirmation."""


class SpendCapReached(RuntimeError):
    """The Google project has hit its monthly spending cap.

    Deliberately NOT retried and deliberately allowed to propagate out of
    generate(). A per-minute rate limit is worth waiting out; a monthly spend
    cap is not - it will still be there in thirty seconds, and every remaining
    image in the batch will fail exactly the same way. Retrying it just turns
    one clear error into dozens of confusing ones. This is the failure that
    stopped projects 14, 15 and 16 mid-set on 21 Aug 2026.
    """


# ============================================================ comparison sheet
# Standing requirement: every render ships a before/after sheet to cross-verify
# against. generate() fills this ledger; the sheet is written on exit.
_LEDGER = []             # [(label, before_path, after_path), ...]
_sheet_hooked = False    # atexit registered? (lazily, so import stays side-effect free)
_sheet_written = []      # paths of sheets written this run
_sheet_attempted = False  # a sheet was already built, or deliberately turned off


def _sheet_enabled():
    return os.environ.get("COMPARISON_SHEET", "1").strip().lower() not in (
        "0", "no", "off", "false")


def disable_comparison_sheet():
    """Turn off the automatic sheet for this run - for a script that writes its own.

    Not a way to skip the standing requirement: a render still has to ship a sheet.
    """
    global _sheet_attempted
    _sheet_attempted = True


def record(before, after, label=None, replaces=None):
    """Register a source/result pair for this run's comparison sheet.

    generate() calls this for you. Call it directly when the delivered file is
    not what generate() wrote - a padded source, a cropped or composited result -
    so the sheet compares the real original against the real delivery:

        raw = rc.generate(padded, prompt, work_base)     # records padded -> raw
        crop_back(raw, ..., final)
        rc.record(original_src, final, replaces=raw)     # corrects the pair

    `replaces` drops any earlier entry whose result path matches, so the raw
    intermediate does not also appear on the sheet.
    """
    if replaces:
        target = os.path.abspath(replaces)
        _LEDGER[:] = [e for e in _LEDGER if os.path.abspath(e[2]) != target]
    _LEDGER.append((label or _view_name(after), before, after))
    _hook_sheet()


def forget(after):
    """Drop a recorded pair by its result path - e.g. a render that got binned."""
    target = os.path.abspath(after)
    _LEDGER[:] = [e for e in _LEDGER if os.path.abspath(e[2]) != target]


def _view_name(path):
    try:
        return _cs().display(path)
    except Exception:
        return os.path.splitext(os.path.basename(path))[0]


def _cs():
    """Import the shared sheet builder, which lives next to this file."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import comparison_sheet
    return comparison_sheet


def _hook_sheet():
    global _sheet_hooked
    if not _sheet_hooked and _sheet_enabled():
        atexit.register(_sheet_on_exit)
        _sheet_hooked = True


def _default_sheet_path():
    """<output folder of the last render>/_Before After - <script name>.jpg

    Keyed to the script so a re-run replaces its own sheet instead of piling up,
    and two different scripts in one estate keep separate sheets.
    """
    outdir = os.path.dirname(os.path.abspath(_LEDGER[-1][2]))
    stem = os.path.splitext(os.path.basename(sys.argv[0] or "render"))[0] or "render"
    return os.path.join(outdir, "_Before After - %s.jpg" % stem)


def write_comparison_sheet(out=None, title=None, before_label="SOURCE",
                           after_label="RENDER", per_sheet=None, pairs=None):
    """Write the sheet for everything rendered so far. Returns the paths written.

    Safe to call explicitly at the end of a script; the exit hook then skips it,
    whether this call succeeded or not - one failure report is enough.
    Never raises - a sheet problem must not look like a render failure.
    """
    global _sheet_attempted
    pairs = pairs if pairs is not None else list(_LEDGER)
    if not pairs:
        return []
    _sheet_attempted = True
    try:
        cs = _cs()
        out = out or _default_sheet_path()
        if title is None:
            estate = os.path.basename(os.path.dirname(
                os.path.dirname(os.path.abspath(pairs[-1][2]))))
            title = "%s  ·  Before / After" % estate if estate else "Before / After"
        written = cs.sheet(pairs, out, title, before_label, after_label,
                           cs.PER_SHEET if per_sheet is None else per_sheet)
        _sheet_written.extend(written)
        return written
    except ImportError:
        print("!! comparison sheet skipped: Pillow is not installed "
              "(pip install pillow). The renders themselves are fine.", flush=True)
    except Exception as e:
        print("!! comparison sheet failed: %s: %s" % (type(e).__name__, e), flush=True)
    return []


def _sheet_on_exit():
    if _sheet_attempted or not _LEDGER or not _sheet_enabled():
        return
    print("\n---- comparison sheet (standing requirement: cross-verify every render) ----",
          flush=True)
    write_comparison_sheet()


def encode(path):
    ext = path.rsplit(".", 1)[-1].lower()
    if ext not in MIME:
        raise ValueError("unsupported image type: %s" % path)
    with open(path, "rb") as f:
        return {"inlineData": {"mimeType": MIME[ext],
                               "data": base64.b64encode(f.read()).decode()}}


def image_dims(path):
    """(width, height) read from a PNG or JPEG header, or None. Standard library only."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                m = marker[1]
                if m == 0xFF:                      # fill byte: re-sync on the next 0xFF
                    f.seek(-1, 1)
                    continue
                if m == 0x01 or 0xD0 <= m <= 0xD8:  # stand-alone markers carry no length
                    continue
                seg = struct.unpack(">H", f.read(2))[0]
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                         0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", f.read(5)[1:5])
                    return w, h
                f.seek(seg - 2, 1)
    except Exception:
        return None


def size_tier(width, height):
    """Which of 1K / 2K / 4K an image of this pixel size belongs to."""
    long_side = max(width, height)
    for tier, limit in _TIER_LONG_SIDE:
        if long_side < limit:
            return tier
    return "4K"


def _report_delivered_size(tag, path, requested):
    """Print the delivered pixel size and warn loudly if it is not the requested tier.

    This is where a silently ignored imageSize would show up. The file is already on
    disk and billed by then, so it is a warning rather than a failure - but it must not
    pass unnoticed: a 1K request that comes back at 4K costs ~1.8x, and a 4K request
    that comes back at 1K is not the approved upscale.
    """
    dims = image_dims(path)
    if not dims:
        return
    got = size_tier(*dims)
    line = "   [%s] delivered %dx%d (%s requested)" % (tag, dims[0], dims[1], requested)
    if got != requested:
        line += ("\n   !! WARNING: requested %s but the API returned a %s-sized image. Stop "
                 "and check the request shape in _render_common.py before the next render "
                 "- the size parameter may have been ignored." % (requested, got))
    print(line, flush=True)


def check_image_size(image_size, confirmed_4k=False):
    """Normalise image_size and enforce the 1K-first cost guard.

    Returns the normalised size string, or raises. 4K is allowed only when
    confirmed_4k is the literal boolean True - a merely truthy value such as 1,
    "yes" or a non-empty list is deliberately NOT accepted, so the expensive
    path cannot be reached by accident.
    """
    size = str(image_size).strip().upper()
    if size not in SIZES:
        raise ValueError("image_size must be one of %s, got %r"
                         % (", ".join(SIZES), image_size))
    if size == "4K" and confirmed_4k is not True:
        raise FourKNotConfirmedError(
            "REFUSING to render at 4K.\n"
            "4K requires explicit user confirmation per the standing render policy:\n"
            "  \"Always render edits in 1K first, then enhance to 4K only after explicit "
            "confirmation.\"\n"
            "All drafts, edits and revisions stay at %s to reduce cost.\n"
            "Once - and only once - the user has approved a 1K image, upscale it with\n"
            "  python upscale_to_4k.py --confirmed <approved image>\n"
            "or call generate(..., image_size=\"4K\", confirmed_4k=True) with confirmed_4k "
            "set to the literal True (a merely truthy value is rejected)."
            % DEFAULT_IMAGE_SIZE)
    return size


def generate(src_path, prompt, out_base, image_size=DEFAULT_IMAGE_SIZE, aspect=None,
             model=MODEL, attempts=3, confirmed_4k=False, compare_src=None,
             compare_label=None, refs=None):
    """Image-to-image render of src_path with prompt, written to out_base.<ext>.

    image_size defaults to "1K" per the standing policy; "4K" is refused unless
    confirmed_4k=True. Returns the written path, or None if every attempt failed.

    Each success is recorded for this run's comparison sheet, which is written
    automatically when the script exits. Pass compare_src to pair the sheet
    against the true original when src_path is a prepared intermediate (a padded
    or pre-cropped copy), and compare_label to name the row.

    refs: optional extra image paths sent AFTER src_path and before the prompt,
    for style, mood, scale or camera reference. src_path stays IMAGE 1 and stays
    the authority on geometry; the refs arrive as IMAGE 2, IMAGE 3 and so on, in
    the order given. Wording alone does not transfer a property like scale or
    lighting between images - showing the model a second picture does - but the
    prompt must then say plainly which single property to take from it and that
    its layout and camera are to be ignored, or the ref starts leaking into the
    geometry. Only the comparison-sheet pair is unaffected: the sheet still
    pairs src_path (or compare_src) against the result, never a ref.
    """
    size = check_image_size(image_size, confirmed_4k)
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY not set in the environment")

    image_config = {"imageSize": size}
    if aspect:
        image_config["aspectRatio"] = aspect
    parts = [encode(src_path)]
    for r in (refs or []):
        parts.append(encode(r))
    parts.append({"text": prompt})
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": image_config,
        },
    }).encode()

    outdir = os.path.dirname(os.path.abspath(out_base))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    url = URL % (model, key)
    tag = os.path.basename(src_path)
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            data = json.load(urllib.request.urlopen(req, timeout=900))
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429 and "spend" in body.lower():
                raise SpendCapReached(
                    "The Google project has hit its monthly spending cap - no "
                    "further renders will succeed until it is raised or the month "
                    "rolls over.\n"
                    "Raise or check it at https://ai.studio/spend\n"
                    "This attempt was rejected at the quota gate rather than "
                    "generated, so it should not be billed.\n"
                    "Files already written are unaffected.")
            wait = 30 if e.code in (429, 503) else 12
            print(f"   [{tag}] attempt {i}: HTTP {e.code} {body}", flush=True)
            if i < attempts:
                time.sleep(wait)
            continue
        except Exception as e:
            print(f"   [{tag}] attempt {i}: {type(e).__name__} {e}", flush=True)
            if i < attempts:
                time.sleep(12)
            continue
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline:
                    ext = "jpg" if "jpeg" in inline["mimeType"] else "png"
                    dst = out_base + "." + ext
                    with open(dst, "wb") as f:
                        f.write(base64.b64decode(inline["data"]))
                    record(compare_src or src_path, dst, compare_label)
                    _report_delivered_size(tag, dst, size)
                    return dst
        fr = [c.get("finishReason") for c in data.get("candidates", [])]
        print(f"   [{tag}] attempt {i}: no image (finish={fr}) "
              f"{json.dumps(data)[:250]}", flush=True)
        if i < attempts:
            time.sleep(12)
    return None
