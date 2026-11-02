# sketch-to-photoreal-render

A [Claude Code](https://claude.com/claude-code) skill that turns an architectural drawing into a
photoreal, DSLR-style render with Google's Gemini image model, while keeping the design exactly as
drawn.

It takes a hand sketch, an elevation, a SketchUp or Revit export, a coloured site plan or the first
page of a PDF sheet. Claude reads the drawing and writes the brief, so you never write an image
prompt. Every billed call needs your yes, 1K comes first, and 4K is made for one approved image only.

## What it does

- **Keeps the drawing's frame.** The script extends the drawing's edges to the nearest aspect ratio
  the model supports, renders at that ratio, then crops the drawing's own rectangle back out. If the
  model re-frames the picture anyway, the pass is flagged.
- **Writes a comparison sheet after every pass.** Drawing and render side by side (or previous and
  revised), so geometry, element counts and materials can be checked before anything is delivered.
  Claude opens each sheet and reviews it against a six-point checklist: redesign, re-frame, invented
  text, added objects, swapped materials, re-solved roof.
- **Asks before spending.** Without the `--spend-ok` flag the script prints the estimate and stops,
  without reading the key. Claude adds the flag only after you say yes to the quoted image count,
  size and cost.
- **Draft at 1K, finish once at 4K.** Revisions and local patches stay at 1K. 4K runs only for one
  image you approved by name, and a 4K file is never revised.
- **Never overwrites.** Each pass gets a new file (`_rev02`, `_rev03` ...), and a job ledger records
  every attempt and its list-price cost.
- **Keeps the key out of chat.** The skill never asks for, accepts or prints your API key. The key
  lives in an environment variable on your own computer.

## What it cannot do

It keeps the drawing's own camera. It cannot show another side of the building, a new angle, a
zoom or crop, or turn a floor plan into an eye-level view. For a new view, export that view from
the 3D model and render the export.

## What you need

- Claude Code on your own computer (the desktop app's Code tab or the `claude` CLI), on a Claude
  plan that includes it. The skill cannot render in claude.ai chat or in the Claude API skills
  container: neither can reach Google or hold the key safely.
- A Google AI Studio API key in a project with **billing on** (image models have no free tier) and
  a monthly spend cap.
- Python 3.9 or later, with Pillow (and PyMuPDF if you want PDF input), from
  `scripts/requirements.txt`.
- Century Gothic for the sheet labels (on Windows it comes with Microsoft Office). On macOS or Linux
  the script also finds URW Gothic. The setup check tells you which font it found.

## Install

1. Download this repository (**Code > Download ZIP**) and unzip it, or clone it.
2. Copy the folder `sketch-to-photoreal-render` (the one that holds `SKILL.md`) into your personal
   skills folder:
   - Windows: `%USERPROFILE%\.claude\skills\`
   - macOS / Linux: `~/.claude/skills/`

   `SKILL.md` must end up at `...\.claude\skills\sketch-to-photoreal-render\SKILL.md`, with no
   extra folder level.
3. Install the Python packages:
   ```
   python -m pip install -r "%USERPROFILE%\.claude\skills\sketch-to-photoreal-render\scripts\requirements.txt"
   ```
4. Save your Google key as a user environment variable named `GOOGLE_API_KEY`, in your own
   terminal, never in a chat with Claude.
5. Restart Claude Code, type `/skills` and check that `sketch-to-photoreal-render` is listed.
6. Ask Claude for a setup check and a free dry run on the bundled test sketch before your first
   real render.

[SETUP.md](SETUP.md) walks through every step with screenshots, including the key, the spend cap,
the dry run and your first render. The same guide is in [docs/Setup guide.pdf](<docs/Setup guide.pdf>)
to download or print.

## Cost

Google's list prices for `gemini-3-pro-image` when this was written (October 2026). Check Google's
current pricing before relying on them.

| Pass | List price per image | Quoted as (up to 2 attempts) |
|---|---|---|
| 1K render, revision or patch | USD 0.134 | up to USD 0.268 |
| 2K render | USD 0.134 | up to USD 0.268 |
| 4K of one approved image | USD 0.24 | up to USD 0.48 |

Every attempt is billed, including one that returns no image. Google also bills each attempt's
input image (about USD 0.0011), the prompt and the model's thinking tokens, so the real charge runs
slightly above the quote. The true bill is in Google AI Studio.

## What is in the folder

| Path | What it is |
|---|---|
| `SKILL.md` | The skill: policy, spending gates, the workflow for one view, commands and errors |
| `scripts/render.py` | The command-line tool: `check`, `render`, `revise`, `patch`, `upscale`, `sheet`, `status` |
| `scripts/_render_common.py` | The Gemini call, the prompts and the 4K guard |
| `scripts/comparison_sheet.py` | The before/after sheet builder |
| `references/` | Art direction, failure modes, cost policy, prompts and the sheet review checklist |
| `evals/evals.json` | Test requests for checking the skill's behaviour |
| `assets/test_sketch.png` | A simple test drawing for the free dry run |
| `SETUP.md`, `docs/Setup guide.pdf` and `docs/screenshots/` | The step-by-step setup guide, on the page and as a PDF |

`README.md`, `SETUP.md` and `docs/` travel with the skill when you copy the folder. Claude Code
reads only `SKILL.md` and the files it points to, so they do no harm there.

## Keep private

Client drawings are confidential: the skill tells you once per project that the drawing is sent to
Google's Gemini API, and waits for your go-ahead. Never put a `.env` file or a key in the skill
folder, and never commit your renders, `_work/` or `_jobs/` folders. The `.gitignore` here covers
them.

## Licence

MIT, see [LICENSE](../LICENSE). Made by Snega Raja Sekar.
