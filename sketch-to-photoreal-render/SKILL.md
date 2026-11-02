---
name: sketch-to-photoreal-render
description: Renders architectural sketches, plans and 3D exports as photoreal DSLR images via Gemini, 1K first, with a sheet per pass. Use when a drawing should become a photoreal image, or to revise or 4K one.
compatibility: Claude Code on a local machine (desktop Code tab or CLI). Not for claude.ai chat or the Claude API skills container, which lack open network egress and a secret store. Needs Python 3.9+, Pillow 10.1+, optional PyMuPDF for PDF input, GOOGLE_API_KEY (or GEMINI_API_KEY) as a user environment variable for a billing-enabled Gemini project with a spend cap, and HTTPS access to generativelanguage.googleapis.com.
---

# Sketch to photoreal render

Turn an architectural drawing - hand sketch, elevation, SketchUp or Revit export, coloured site
plan, PDF sheet - into a picture that looks shot on a full-frame DSLR, with the design kept
exactly as drawn. **Gemini makes the pixels** (`gemini-3-pro-image`, legacy `generateContent`).
Your job is everything around that call: read the drawing, write the brief, guard the spend,
and check every result against its source before anything is delivered.

`scripts/render.py` does the mechanics, one model call per pass: it edge-extends the source to
the nearest of the ten aspect ratios the model offers (so the model is never asked to
re-compose), renders at that ratio, crops the source's own rectangle back out, flags any
re-frame, and writes a before/after comparison sheet. Paths below are relative to this skill's
folder; call the script by its absolute path, with the Python that `render.py check` passes on.

## Where this runs

Live rendering needs Claude Code on the user's own machine, with `GOOGLE_API_KEY` set there.
If you have no local shell or file system - claude.ai chat, the Claude API skills container -
say so plainly: you can read the drawing, write the brief and, if Python and Pillow are
present, show a `--prompt-only` prompt, but you cannot render. Never offer to take the key.

## The standing policy - quote it, never paraphrase

The user's render policy, given 28 Aug 2026:

> Task: Render the input image in 1K quality first to reduce cost.
> - Maintain 100% accurate geometry, scale, and ratio.
> - No hallucination, no element addition/removal unless explicitly instructed.
> - Replace materials with real finishes (e.g., terracotta roofs, realistic trees, pools, landscapes).
> - Output must look like high-end DSLR architectural photography.
> - All edits and revisions should remain in 1K quality until confirmed.
>
> Once approved, upscale the same image to 4K quality:
> - Deliver sharp, detailed accuracy with no blur or smudge.
> - Every element must appear real and photorealistic when zoomed in.
> - Preserve exact geometry and detail fidelity from the reference image.
>
> Final rule: Always render edits in 1K first, then enhance to 4K only after explicit confirmation.

The user's comparison-sheet requirement, given 31 Aug 2026:

> in all the future render, after every render i want comparison sheet to cross verify.
> update everywhere.

If you restate either one, quote it. Cost figures and background: `references/policy.md`.

## Hard gates

1. **Ask before spending.** Before any billed call, tell the user the image count, the tier
   and the cost, and wait for an explicit yes. Only then add `--spend-ok`. The script enforces
   this: without `--spend-ok` it prints the estimate and exits 3 without reading the key. A yes
   covers exactly what you quoted; each later revision, patch or rerun of a failed pass is a
   new spend, so quote it (one image, 1K, up to USD 0.268) and get a yes again. You may put the
   plan and the price in one message ("Next: revise view 02 to fix the roof colour - 1 image
   at 1K, up to USD 0.268. Go ahead?"). Quotes are at the image rate; Google also bills each
   attempt's input image (about USD 0.0011), the prompt text and the model's thinking tokens,
   so say the real charge runs slightly above the quote.
2. **4K is per image, after approval.** Run `upscale --confirmed` only for one image the user
   has seen on its comparison sheet and approved by name. "Looks good" on a set is not approval
   to take the set to 4K, and "make it sharper" is not approval to re-render at 4K - ask which
   single image. Quote it like any spend: the file name, 1 image, 4K, up to 2 attempts, max
   USD 0.48 (USD 0.24 per attempt).
3. **Never iterate at 4K.** Fix everything at 1K first; the 4K pass reproduces faults
   faithfully. A 4K file is final and is never revised.
4. **Every pass ships its sheet, and you review it first.** After each pass, open the sheet
   image with the Read tool and review it with `references/review-checklist.md`. Decide a
   verdict (match / minor / major) with the issues you see, then hand over the render, the
   sheet, and what the sheet shows. A render without its sheet is not finished.
5. **Never overwrite, and never write into this skill folder.** The script never reuses a file
   name and refuses an output folder inside the skill; do not move, rename or replace
   delivered files or sources yourself.
6. **Never handle the API key in chat.** Do not ask for it, accept it, print it, or write it
   into a file. If a user pastes one, say it is now exposed in the chat, that they should
   delete and recreate it in AI Studio, and how to set the new one as an environment variable.
   Prefer the user environment variable to a `.env` file, and never put a `.env` in a skill
   folder that is copied, zipped or uploaded.
7. **Say once per project, before the first live call, that the drawing is sent to Google's
   Gemini API** (generativelanguage.googleapis.com) to be rendered. Client drawings are
   confidential; get the user's go-ahead.
8. **Every retry is billed**, including attempts that return no image. Fix the prompt; never
   raise `--attempts` to rescue a bad one (the script caps it at 3).

## What this skill cannot do

The pipeline keeps the drawing's own camera. It cannot show another side of the building, a
new angle, a zoom, a crop or a different aspect ratio, and it cannot turn a floor plan into a
perspective or eye-level view: in the tree, a plan sent as a picture came back as a different
house, and prompt-only camera moves gave a different villa each time (`references/art-direction.md`
section 13). When the user asks for any of that, do not spend: explain it, and ask for a new
export of that view from the 3D model, then render that export as a new job. Never put camera
or framing changes in `revise` or `patch` notes; the script prints `!! CAMERA / FRAMING WORDS`
if you do.

It also does not erase labels, register panels, tile steep aerials or composite background
plates, which the tree did around its renders (`references/failure-modes.md`). Where those
were what worked, warn the user before spending that wording alone may not be enough.

## Setup check (once per machine)

Run `python scripts/render.py check`. It prints the Python, Pillow and PyMuPDF versions, the
sheet font, the model id, and where the key was found (the source only, never the value); with
no key it prints the steps to set one. If it fails on an import, run
`python -m pip install -r scripts/requirements.txt` with that Python. With a key in place,
`check --online` makes the free `models.get` metadata call to prove the key and model work; it
is never billed.

## Workflow for one view

### 1. Intake

Get from the user: the file **as a path on disk** (a pasted image has no path - ask where the
file is), a view name, and notes in four fields - **materials**, **lighting**,
**environment**, **other** (each optional). Ask about anything the drawing leaves open that
would change the picture (is this flat area lawn or paving? which way does the sun come from?)
instead of guessing. Triage the input:

- A sheet with several panels (floors, elevations), or a PDF whose view is not on page 1:
  have one panel or page exported, or crop it yourself into a new file in a `... Input`
  folder, one view per job. Tell the user the comparison sheet pairs that panel with its
  render. Dense furniture layouts failed generatively in the tree; say so before spending.
- A request the pipeline cannot honour (see above): stop and explain before any spend.
- A sheet with a title block, area schedule, labels or statutory boundary lines: these must
  stay exactly as drawn, and the model cannot keep text (the brief forbids it). Have them
  cropped off before rendering and placed back unchanged on the final sheet outside the
  render; name any statutory line in a caution so it is not turned into a wall or erased.
- A request that contradicts the drawing (a flat roof where a hipped one is drawn): point it
  out and ask. The policy keeps the geometry as drawn unless the user explicitly says otherwise.

### 2. Read the drawing and write the brief

Run a free `--prompt-only` pass first, always with `--out` (outside this skill folder; for
`assets/test_sketch.png`, a scratch folder): it rasterises a PDF's page 1 and writes the padded
feed to `<out>/_work/prompt-only/<view>_<tier>_padded.jpg` (at most 2400 px), the easiest file
to look at. Open it with the Read tool and study it. Then write the brief JSON following
`references/art-direction.md`:

```json
{"elements": ["two-storey block, hipped roof, left half of the frame", "..."],
 "finishes": ["warm off-white lime plaster walls", "..."],
 "cautions": ["FRAMING: villa spans 20-78% of width, eave at 37% height; if it grows, re-centres or sky is added, the result has failed", "..."]}
```

- `elements`: every building element, opening, roof form, level, railing, pool, paving area,
  planting mass and furniture item, with its position and its count (max 30 items, 160 chars).
- `finishes`: the real materials (max 15, 120 chars).
- `cautions`: the measurable framing anchor FIRST, with its "the result has failed if ..."
  test; then storey counts, drafting artefacts that are not objects, and negatives specific to
  this frame (max 10, 160 chars).

Keep the brief short - long briefs lost framing in the tree. Save it next to the job, e.g.
`<out>/_briefs/<view>.json`. Longer material or setting text belongs in `--materials` /
`--environment` (notes may total 4000 characters).

### 3. Choose the flags

- Roofs are not terracotta (flat slabs, membrane, slate, metal, green roof)? Add
  `--no-terracotta-example`, put a roof caution in the brief ("all roofs are flat - no tiles,
  no pitch, no terracotta", or "the wing roof is a flat slab - no tiles, no pitch") and name
  the real roof finish. The shared fidelity brief uses terracotta as its example finish and
  has added red tiled roofs to flat-roofed villas; the flag removes that positive example. A
  caution may still name terracotta as a negative.
- Default tier is 1K. Suggest `--size 2K` (same list price) only when key elements would be
  under about 20 px across at 1K, as on a wide estate aerial, and use it only after the user
  agrees; 4K is never a draft tier.
- The input is a prepared copy (axis lines cleaned, labels erased, a white void pre-filled)?
  Pass the untouched export as `--original FILE` so the sheet pairs the true original.
- `--out` defaults to a sibling `03 Output` when the input sits in an `... Input` folder,
  else `<input folder>/03 Output`; it may never be inside this skill folder.

### 4. Audit the prompt (free)

Re-run with the brief and notes and `--prompt-only`, read the printed prompt, and check that
nothing in it asks for an element the drawing does not have.

### 5. Estimate, ask, render

Run the command without any gate flag to get the estimate (exit 3), quote it to the user, and
wait for a yes. Then run it again with `--spend-ok`. A live call usually takes 20-60 s, but
one attempt may wait up to 15 minutes, longer than a foreground Bash call: run live passes in
the background (`run_in_background`) and wait for them. If a live command is cut off, run
`render.py status`, report the interrupted pass as possibly billed, and ask before any rerun.
Several views: quote the batch total (views x 1K x up to 2 attempts) and get one yes for the
batch, then run the views one after another.

### 6. Review the sheet

Open `<out>/_Before After - <view>_1K.jpg` with the Read tool. Follow
`references/review-checklist.md`: framing and proportions, counts, openings, roof form,
storeys, added or missing objects, text, materials, realism. An orange "aspect a -> b
(framing changed)" note, or a WARNING line from the script, means the model re-framed: that
render cannot be revised or approved, so render again from the source with a stronger
framing anchor and a caution naming exactly what the failed pass did ("PREVIOUS ATTEMPT
FAILED: ..."). If two 1K renders of a view re-frame, stop and report rather than re-roll.
Open the render itself when the sheet is too small to judge a detail.

### 7. Report

Give the user: the render path, the sheet path, your verdict with the issues you found, the
cost (`render.py status` shows it), and the choices - approve this image for 4K, revise one
thing, patch one region, or render again from the source.

### Revise loop (stays at 1K)

`revise "<current render>" --notes "<one change>"`. Rules:

- One change per pass. Several changes in one edit tend to regenerate the whole frame.
- Describe the target state of the object, not the correction ("the entrance door is solid
  warm-bronze timber with two vertical pull bars", not "fix the door"). Zoom in on the render
  before writing it: a recolour is not an addition.
- The before is the image being revised; the sheet pairs it against the new file
  (`BEFORE · <view>_1K` / `AFTER · <view>_1K_rev02`).
- Only the current file (the newest non-4K pass of the job) can be revised; the script names
  it if you pick another. A revision of a 2K render is made at 1K and named `_1K_revNN`.
- When the composition itself is wrong (camera moved, subject grew, re-frame warning), do not
  revise: run `render` again from the source with a better brief.

### Patch (a local fix, stays at 1K)

`patch "<current render>" --box x0,y0,x1,y1 --notes "<the change>"` with the box as
fractions of the frame (0,0 top-left). The box is cropped, edited at full 1K, scaled back and
pasted with a 36 px feather on edges inside the frame; every pixel outside the box stays
byte-identical. Use it for one object or one area (an invented wall, a wrong plant, a door).
Say what must change and that it must be clearly visible; do not tell it to keep the very
thing you want changed. Each side of the box must be at least 72 px.

### 4K (one approved image)

When the user has approved one named image and its quoted price: `upscale "<that file>"
--confirmed`. Without `--confirmed` the script refuses (exit 2) and prints what approving that
file would cost - use that for the quote. It refuses unless the file is the current pass of
its job, has its sheet, carries no warning and has the source's shape, and it refuses a second
4K of the same image unless the user asks and you pass `--force`. The approved image is the
reference; it is padded, rendered at 4K with a resolution-only prompt that locks its finishes,
cropped back, and paired against it on an `APPROVED 1K · x / 4K · y` sheet. The approved file
is never touched. The 4K prompt carries the first render's notes and lists each later change
as already made; read it with `--prompt-only` first. Review the 4K sheet too: resolution
should change and nothing else - zoom into foliage and fine texture for mush or smear, and
check that no revised element was doubled.

## Command reference

```
python scripts/render.py check [--online]
python scripts/render.py render <input> [--name VIEW] [--out DIR] [--brief brief.json]
        [--materials T] [--lighting T] [--environment T] [--other T] | [--notes T | --notes-file F]
        [--original FILE] [--no-terracotta-example] [--size 1K|2K] [--attempts N]
        [--dry-run | --prompt-only | --spend-ok]
python scripts/render.py revise <current render> (--notes T | --notes-file F)
        [--dry-run | --prompt-only | --spend-ok]
python scripts/render.py patch <current render> --box x0,y0,x1,y1 (--notes T | --notes-file F)
        [--dry-run | --prompt-only | --spend-ok]
python scripts/render.py upscale <approved render> --confirmed [--force] [--dry-run | --prompt-only]
python scripts/render.py sheet <render>      # rebuild that pass's sheet, local and free
python scripts/render.py status [DIR]        # jobs, passes, warnings, attempts, cost
```

- The four field flags and `--notes` / `--notes-file` are alternatives; the script refuses a
  mix, and `--notes` with `--notes-file`.
- `--prompt-only`: builds the feed and prints the exact prompt; sends nothing, reads no key,
  records no pass.
- `--dry-run`: no API call; a stamped "DRY RUN" stand-in goes through the real crop-back,
  sheet and ledger path. Use a scratch `--out` folder so stand-ins never sit beside real work.
  A live pass never starts from a dry-run file.
- Files: `<view>_1K.png`, `<view>_1K_rev02.png`, `<view>_1K_rev02_4K.png`; a clash gets
  ` (2)`. Sheets: `_Before After - <file stem>.jpg`. Work files (padded feed, raw frame,
  prompt) in `_work/`; the job ledger in `_jobs/<view>.json`. A PDF, an EXIF-rotated photo or
  a PNG with a transparent background becomes an upright PNG on white in `_work/` that is the
  source of record.
- Environment: `IMAGE_SIZE` (1K default, 2K allowed, 4K refused), `ATTEMPTS` (default 2,
  max 3), `MODEL` (default `gemini-3-pro-image`; letters, digits, `.`, `_`, `-` only).

Exit codes: 0 done; 1 error; 2 refused by a gate or bad arguments (nothing spent); 3 spend
gate, estimate printed; 4 delivered but needs attention (re-framed, lineage warning, wrong
size tier, or no sheet).

## Error handling

The ledger books an attempt as billed when Google answered HTTP 200 (with or without an
image), or when a request was sent and no answer was read; HTTP error responses and requests
that never left the machine are booked at USD 0. `status` shows list-price estimates; the real
bill is in AI Studio.

| What you see | What it means and what to do |
|---|---|
| `No Gemini API key found` (exit 1), or `key : NOT FOUND` from `check` | Tell the user to set `GOOGLE_API_KEY` as a user environment variable themselves (the message gives the Windows and macOS/Linux steps), restart Claude Code, run `check`. Never ask for the key. |
| `HTTP 400` ... `API key not valid` | The key is wrong or was revoked. The user re-creates it in AI Studio and sets it again; never ask for it. |
| `HTTP 400` (other) | The request was rejected: model id wrong for this endpoint, or a malformed or oversized input. Run `check --online`; do not retry blindly. |
| `HTTP 401` / `403` | 401: the key is invalid or expired. 403: the key lacks permission, for example an older key not restricted to the Gemini API. The user creates a new key in AI Studio and sets it again; never ask for it. |
| `HTTP 400 FAILED_PRECONDITION`, or `HTTP 429` naming a free-tier quota with `limit: 0` | Billing is not on for the key's project, and image models have no free tier. The user enables billing in AI Studio. Waiting will not fix it; do not rerun until they confirm. |
| `HTTP 404` | The model id is not served to this key. `check --online`; `MODEL` overrides the id. |
| `MODEL ... is not a valid model id` | A stray space or quote in the `MODEL` variable. Fix or remove it; nothing was sent. |
| `SpendCapReached` | The Google project hit its monthly spend cap; nothing more will render until the user raises it at aistudio.google.com/spend or the month rolls over. Stop the batch and tell them. |
| `HTTP 429` (no "spend", no free-tier `limit: 0`) | Rate limit. Report the failure and what `status` booked, wait a few minutes, quote the rerun (1 image, 1K, up to USD 0.268) and get a new yes. An earlier yes does not cover a rerun. |
| `HTTP 500` / `503` | Google-side error, booked as not billed. Report it, quote the rerun and get a new yes before trying again. |
| `no image (finish=['IMAGE_SAFETY'])` or another finishReason | The model refused or returned text only; every such attempt was billed. Look for what triggered it (people, text, a reference to a real brand), adjust the notes or brief, then quote and ask before rerunning. |
| `WARNING ... re-framed` / orange aspect note (exit 4) | The model changed the framing. Delivered uncropped; it cannot be revised or approved. Render again from the source with a measurable framing anchor and failure test (`references/art-direction.md`). |
| `... descends from a re-framed render` | Same lineage problem; render again from the source. |
| `WARNING : the API returned a 4K-sized frame` (exit 4) | The size parameter may have been ignored; the pass is priced at the delivered tier. Stop: run no further passes and tell the user. |
| `the image could not be decoded ... truncated or corrupt` | Ask the user to re-export the file. |
| `the output folder ... is inside the skill folder` | Pass `--out` with a folder outside the skill. |
| `!! CAMERA / FRAMING WORDS` | The notes ask a revise or patch to move the camera. Do not spend; see "What this skill cannot do". |
| `Pillow is not installed` / `No module named PIL` | `python -m pip install -r scripts/requirements.txt` with the Python that runs the script. |
| `PDF input needs PyMuPDF` | `pip install pymupdf`, or export page 1 as PNG and render that. |
| `not the current render` / `not a render this tool delivered` | Use the file the message names; a file from elsewhere starts a new job with `render`. |
| `has no comparison sheet` | Run `sheet <file>`, review the sheet with the user, then upscale. |
| `running/interrupted` in `status` | A live command was cut off; the attempt may have been billed. Report it and ask before any rerun. |

## References

- `references/policy.md` - the verbatim policy and sheet requirement, what "confirmed"
  means, list prices, why 1K-first saves money.
- `references/art-direction.md` - how to write the per-view brief, by input type.
- `references/prompts.md` - every prompt constant verbatim, the assembly order, and real
  assembled prompts for render, revise, patch and 4K.
- `references/failure-modes.md` - what went wrong in the tree, why, what worked there and what
  this skill can do about it.
- `references/review-checklist.md` - how to review a comparison sheet and what to report.
