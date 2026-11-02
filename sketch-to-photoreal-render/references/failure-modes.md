# Failure modes

What went wrong in the original render project (the tree), why, and what was done about it. Evidence paths are
in that project's own folders, which do not travel with this skill. "Brief" means the per-view
brief JSON (`art-direction.md`); "re-render" means `render` again from the source.

The Fix column separates two things where they differ. **Tree:** what actually worked in the
estate scripts, which is sometimes a pixel step this skill does not have (erasing, pre-filling,
pasting, tiling). **Skill:** what you can do with `render.py`. Where the tree found that wording
alone failed, tell the user before spending that the skill's fix may not be enough.

## Contents
- Framing and geometry (1-10)
- Invented or lost content (11-19)
- Materials and look (20-28)
- Process and cost (29-35)

## Framing and geometry

| # | Symptom | Cause | Fix | Evidence |
|---|---|---|---|---|
| 1 | Output re-framed when the nearest supported ratio was requested outright (1.0% on wide views, 3.4% on view 02) | The API offers ten fixed ratios; the source's is not one of them | Edge-extend to the nearest ratio, render there, crop the source box back (what `render.py` does); compare with the true original | project 03/render_p03_1k.py; project 14/prep_new02.py |
| 2 | Uniform 1-2% stretch on every delivery | The tier frames are not exactly nominal (21:9 returns 1584x672 = 2.357) | Crop back by fraction, then resample height by under 1% to the source ratio (`crop_back`) | project 14/render_new.py; project 17/render_p17_1k.py |
| 3 | Aerial camera flies in: estate grows, plot edges and context cropped | Long brief with "hero" emphasis; framing lock buried mid-prompt | Tree: measured lock first AND last, a "the result has failed if ..." test, emphasis only through light; when views still flew in, short edit prompts on the ORIGINAL input held. Skill: FRAMING as the first caution with a failure test, short brief; it cannot edit the source, so after two re-framed renders stop and report | project 14/render_new02.py; project 19/p19_brief_av03_rev02.json, p19_brief_av03_rev03.json |
| 4 | Every view re-framed despite strong wording; with no camera words at all, an aerial came back at eye level | An ~800-word brief (padded to 21:9); then an over-lean prompt | Tree: ~120-word brief and one camera-anchor sentence per view (that lean pass sent the raw export without aspectRatio). Skill: brief block about 150 words, one measured framing caution | project 16/render_p16_new_lean.py |
| 5 | Isolated model on a white void squared up into a frontal elevation | Large empty void invites re-composition | Tree: wording failed on all five views; pre-filling the void (sky gradient, the model's lawn colour) plus a KNOWN FAILURE block registered one; the final was tiled over a background plate. Skill: pre-fill a copy, render it with `--original <export>`, say what the void becomes; warn the user first | project 18/render_p18_1k.py:62-66; render_p18_tiled.py |
| 6 | Floor-plan panels came back ~14% taller | Multi-panel sheet squeezed into a standard frame | One panel per call, padded to the nearest ratio and cropped back; the sheet's orange flag catches drift over 2% | project 04/render_p04_flooring.py |
| 7 | Unusual hipped roof re-solved into a textbook L-shaped roof | Model "corrects" unusual geometry | Roof inventory: planes, ridges, hips, valleys, and "do not re-solve it" | project 04/render_p04_flooring.py |
| 8 | Storey added; single-storey blocks rendered two-storey | Model improves massing; prompts rarely change height once wrong | Tree: pasted the design model's own pixels over the wrong blocks, then one edit pass. Skill: state storey counts in the brief from the start; if height is wrong, re-render from the source with the storey caution first, and report if it persists | project 19/prep_av04_rev04.py |
| 9 | A plan sent as the image came back as a different, single-storey building; camera moves from a plan gave a different villa each time | The model read the ground-floor plan as the building's shape; nothing to hold on to when the camera moves | Tree: massing models built from the plan, AI only dressing them. Skill: none - it keeps the drawing's own view; do not spend, ask for a 3D export of the wanted view | project 12/render_b8_view01_birdseye_wide.py; build_b8_massing.py |
| 10 | At 1K a wide estate aerial lost its villas | Each villa was ~15 px across at 1K | Render that frame at 2K (same list price as 1K), after the user agrees | project 12/render_hero_v2.py:55-61 |

## Invented or lost content

| # | Symptom | Cause | Fix | Evidence |
|---|---|---|---|---|
| 11 | Red terracotta hip roofs on a flat-roofed modern villa | Shared fidelity brief names terracotta as its example finish | `--no-terracotta-example` plus "all roofs are flat - no tiles, no pitch" | project 18/render_p18_1k.py |
| 12 | A sports court grew in an aerial that has none | A finish spec for an absent element reads as an instruction to add it | Complete element list; finishes only for listed elements | project 03/render_p03_1k.py |
| 13 | Furniture invented: a table for six beside a four-chair table, a bed on a roof terrace | Model furnishes plausible rooms | Exact counts per area; "NO ..." for the likely invention | project 04/render_p04_flooring.py; project 14/ai9_terrace_sofa.py |
| 14 | Pool on a dry flat garage roof; a second pool and an extra drive | Open slab or open ground read as programme | "No water on any roof"; "EXACTLY ONE pool"; name the only paving | project 14/fix_pass.py; project 19/p19_brief_av03_rev02.json |
| 15 | Invented labels ("07c", "+1.650M", "ROAD"); scale figures, ground labels and awning lettering rendered | Renderer garbles small text; entourage taken literally | Tree: erased every label before rendering, re-typeset afterwards; a remove-labels line alone left a sketch's zone numbers. Skill: "scale figure is entourage - leave it out; no text anywhere"; for labelled sheets, render an erased copy with `--original` and warn the user | project 04/render_p04_flooring.py; project 17/render_p17_1k.py; project 02/render_landscape.py |
| 16 | Boundary wall built along a coloured axis line; magenta wall drawn as a pink line | Drafting colours read as design | Tree: "prompt wording did not stop it" - the line was erased from a copy of the input and the sheet paired the original. Skill: name the artefact in a caution; if that fails, erase it from a copy and render that copy with `--original <export>` | project 19/clean_axis_lines.py:4-6; p19_brief_av03_rev03.json |
| 17 | Grilles appeared on every window | Prompt said "grilles where they occur" | Never mention an element conditionally; describe only what is drawn | project 15/render_17_09_2026_1k.py |
| 18 | Blank recessed panels turned into doors or windows, also at 4K | Panels look like openings; counts not given | Count openings AND blank panels per elevation; "if a panel looks like a doorway, it is not" | project 17/rev5_flank_awnings.py; 4k_prompt_04.txt:25 |
| 19 | Low-contrast element dropped (beige awnings on an ivory wall) | Model resolves faint panels away | Make the colour a shade deeper, ask for its cast shadow; zoom in before re-prompting | project 17/rev4_awning_fix.py |

## Materials and look

| # | Symptom | Cause | Fix | Evidence |
|---|---|---|---|---|
| 20 | Material swaps: a bedroom in teak, oak on a stone terrace, tan plaster piers as orange battens | Model picks an "appropriate" finish per area | One named finish per zone class; say what it is NOT | project 04/render_p04_flooring.py; project 14/render_new02.py |
| 21 | Solid walls rendered as glass; slabs tapered to knife edges | Flat opaque fills read as glazing | "Walls are solid by default; glass is the exception"; constant-thickness slabs | project 03/render_p03_1k.py |
| 22 | Output still reads as CGI despite "photorealistic" | Flat ambient light, perfect arrises, clean glass | Describe physics: hard sun, dark shadow cores, raking-light texture, real glass reflections, construction tolerance | project 17/render_v3_photoreal.py |
| 23 | "New building" pass stripped surface texture; neighbours became flat white CG boxes | Age and realism were doing the same job | Separate AGE (remove stains, moss, chipping) from PHYSICS (keep grain, micro-relief, real light): "New and clean is not the same as flat" | project 17/render_v7_fix.py:9-11 |
| 24 | Whole facade soft; top-down plan looks like a tilt-shift toy | Unqualified "bokeh" / "cinematic depth of field" | Building sharp edge to edge; only far background softens; uniform sharpness on aerials | project 16/render_p16_new2.py; project 12/render_master_layout_02.py |
| 25 | Blotchy, tadelakt-like plaster | "Tonal mottling" taken too far | Smooth, evenly toned plaster with crisp recessed joints | project 14/ai_materiality.py |
| 26 | Glazing full of phantom rooms and doubled columns | Over-strong mirror reflections | Mostly transparent glass with a light sheen | project 14/villa02_tweak.py |
| 27 | Dry-season scrub and bare red earth around the estate | Default landscape | Lush post-monsoon greens matched to the estate's own garden, in a one-fault revision | project 12/render_master_layout_02_rev2.py |
| 28 | A global colour instruction bled onto the roof | "Uniform ivory" applied to every surface | State the roof and joinery exceptions every time | project 17/render_v2_fresh.py |

## Process and cost

| # | Symptom | Cause | Fix | Evidence |
|---|---|---|---|---|
| 29 | A three-part correction regenerated the whole frame (camera dropped) | Too many changes in one whole-frame edit | One change per `revise`; `patch` for a local fix | project 16/render_edits_1k_rev3.py |
| 30 | Patch came back almost unchanged | Header said "keep every building exactly as it is" and won over the change | Say the change is required and must be clearly visible; do not protect the thing being changed | project 19/render_p19_1k.py |
| 31 | A re-render repeated the previous attempt's fault | The new prompt did not say what had gone wrong | Name the exact fault seen on the sheet in one caution ("PREVIOUS ATTEMPT FAILED: ..."); a KNOWN FAILURE block registered view 02 of project 18 | project 18/p18_brief_rev02.json:14,25; project 14/fix_pass.py; project 15/render_17_09_2026_1k.py:80 |
| 32 | Reference image donated its layout, camera or whole site plan | References without a single stated job | The source stays authoritative; avoid whole-scene references; describe the style in words | project 12/render_hero3d.py; project 04/render_p04_ref_style.py |
| 33 | Counts drift and a dollhouse look after many stacked edits | Every pass is a photograph of a photograph | After a few revisions, re-render once from the source with all agreed changes - but revise when the composition is right: a re-render from the export recomposed a view whose earlier render was right | project 17/render_v2_fresh.py; render_v5_final.py |
| 34 | Faults in the approved master reproduced faithfully at 4K; a 4K brief could undo an approved scheme | 4K is a resolution pass; the CLI 4K brief carried FIDELITY_PROMPT's terracotta and lawn examples | Fix everything at 1K; the skill's 4K prompt locks the approved finishes and omits the materials paragraph | project 17/fix_0607.py; project 19/upscale_av03_4k.py |
| 35 | Delivered 4K foliage mushy | That 4K was upscaled from a ~1.5K-wide 1K intermediate | The skill's 4K pass also starts from the approved 1K: zoom into foliage on the 4K sheet and report mush rather than re-running 4K | project 14/ai9_native4k.py |

Two more lessons that are not prompt faults: the August 2026 spend cap stopped three estates
mid-set (stop on `SpendCapReached`, never retry it) [_render_common.py], and outputs were
overwritten in place by an edit script [project 02/replace_sea_with_forest.py] - the
skill never reuses a file name.
