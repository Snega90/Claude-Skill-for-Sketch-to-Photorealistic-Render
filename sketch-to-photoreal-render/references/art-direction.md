# Art direction: writing the per-view brief

Every rule below is a lesson from the original render project (the tree); the estate and script that showed it
are cited in brackets. The fidelity brief, notes block, canvas note and framing tail are fixed
(see `prompts.md`); the per-view brief is the part you write.

## Contents
1. What the brief does, and what the skill does not
2. Format and limits
3. Elements: an inventory with counts and positions
4. Framing: a measurable anchor, a failure test, a short brief
5. Finishes: a project material block
6. Finish vocabulary from the Goa / Konkan work
7. Light follows the drawing; new is not flat
8. Drafting artefacts are named non-objects
9. Negatives for this frame only
10. Solid walls, stated storeys, the roof as drawn
11. Depth of field, bounded
12. What goes in the notes fields
13. By input type
14. A worked example

## 1. What the brief does, and what the skill does not

`render.py --brief` appends it to the prompt as a checklist after the user's notes:
`SKETCH ELEMENT INVENTORY` (every listed element must appear, in place and proportion, and
nothing else may be added), then `FINISHES TO USE`, then `TAKE SPECIAL CARE`. The model then
reads the canvas note and, last, the framing lock. The brief is how a generic fidelity prompt
becomes a prompt about this drawing.

The tree's biggest quality lever was "NOT prose quality but deterministic scaffolding around one
1K call per view: crop to one floor/view, pad to native ratio, erase text, render, crop back,
register, fix locally by compositing, re-typeset labels, compare on a sheet. Copy the workflow,
not just the prompt." [early sweep: project 04]. The skill pads, crops back, patches and
writes the sheet; it does not erase text, register, composite or re-typeset, and the brief
cannot make up for that - when a view needs those steps, tell the user before spending.

## 2. Format and limits

```json
{"elements": ["..."], "finishes": ["..."], "cautions": ["..."]}
```

Up to 30 elements of 160 characters, 15 finishes of 120, 10 cautions of 160; the block is capped
at 3000 characters. The script refuses a brief that breaks a limit rather than cutting it. Put
long material or setting text in `--materials` / `--environment` instead.

## 3. Elements: an inventory with counts and positions

- List every distinct building element, opening, roof form, level, railing, pool, paving area,
  planting mass and furniture item, each with its position (left / centre / right, foreground
  / background, or % of width and height) [the hosted version (providers.py), _BRIEF_SYSTEM].
- Give counts as numbers: windows per elevation, columns, louvre panels, loungers, palms,
  steps. "exactly 1 dining table with 8 chairs" held where "the furniture" drifted
  [project 04/render_p04_flooring.py]; element counts drift on stacked edits
  unless stated [project 17/render_v2_fresh.py].
- Count blank panels as well as openings: a 4K attempt turned three tall blank recessed panels
  into arched doorways [project 17/4k_prompt_04.txt:25; rev5_flank_awnings.py].
- Make the list complete. A finish described for an element that is not in the frame reads as
  an instruction to add it - a sports court grew in an aerial with no court [project 03/render_p03_1k.py].
- Never mention an element "where it occurs": "slim dark metal grilles where they occur"
  produced grilles on every window [project 15/render_17_09_2026_1k.py].
- Measure what you state. Check heights and positions on the feed before writing them; an
  inventory that enlarges a tree or moves a window asks the model to do the same.

## 4. Framing: a measurable anchor, a failure test, a short brief

The pad-and-crop path stops most re-framing, but a long brief can still fly the camera in or
enlarge the subject [project 14/render_new02.py; project 19/p19_brief_av03_rev02.json].

- Make the FRAMING caution the first caution. It measures the frame: where the subject spans
  (% of width), where the eave, horizon or ground line sits (% of height), what touches an edge
  [project 14/build_new02_prompts.py; project 12/render_b8_entrance_rev5.py]. The tree put the
  lock first AND last [project 14/render_new02.py]; the skill's prompt ends with a generic lock.
- Add a failure test the model can check: "if the villa takes up more than 15% of the frame
  width, or the bridge disappears, the result has failed" [project 19/p19_brief.json].
  Numbers are checkable; descriptions are not [project 17/render_v2_fresh.py].
- Empty ground and sky are part of the composition: "Whatever is empty ground, open land, road
  or sky in the input stays empty ground, open land, road or sky in the output, occupying the
  same share of the frame" [project 14/render_new02.py]. Awkward framing is correct framing
  [project 17/render_v2_fresh.py].
- Never use "hero" or emphasis wording; restrict emphasis to light and sharpness [project 19/p19_brief_av03_rev02.json].
- Keep the brief block to about 150 words. An ~800-word brief lost framing over four rounds;
  ~120 words with one camera-anchor sentence per view held it. Too lean is also wrong: with
  no camera words the model picked its own viewpoint [project 16/render_p16_new_lean.py].
- Anchors are not a guarantee: project 19's AV03 views (1) and (3) flew the camera in "despite the
  framing lock placed first and last", and short edit prompts on the ORIGINAL inputs held [project 19/p19_brief_av03_rev03.json]. The skill cannot send an edit prompt on the source, so
  after two re-framed renders of one view, stop and report instead of re-rolling.
- Re-rendering after a failed pass: add one caution naming exactly what the previous attempt
  did wrong, from your sheet review ("PREVIOUS ATTEMPT FAILED: it enlarged the villa and cut
  off the gate - keep both as drawn"). A KNOWN FAILURE block is what registered view 02 of project 18 [project 18/p18_brief_rev02.json:14,25; project 14/fix_pass.py; project 15].

## 5. Finishes: a project material block

- The fidelity brief's example finishes are terracotta tiles, real trees and lawns, pool water,
  lime plaster, timber, glass and stone. When the architecture differs, drop the terracotta
  example (`--no-terracotta-example`) and name the real finishes: a flat-roofed villa came back
  with red tiled hip roofs while that line was in the prompt [project 18/render_p18_1k.py;
  project 03/render_p03_1k.py].
- Decide what each SketchUp colour or hatch means before rendering. Tan bands were plaster
  piers, not timber; a scalloped hatch was real fan-laid granite setts, not a placeholder [project 14/render_new02.py].
- Name the colour and say what it is NOT: "warm sand plaster - not green, not yellow"; "matt
  mustard paint - NOT metallic gold" [project 14/fix_pass.py; project 17/
  render_p17_1k.py].
- One finish per zone class. Rooms swapped to teak and terraces to oak when finishes were left
  to the model [project 04/render_p04_flooring.py].
- State exceptions to a global colour every time: "uniform ivory" bled onto a slate roof [project 17/render_v2_fresh.py].
- Keep the drawn colour: "stone walls keep the colour drawn in each view ... never recolour to
  red laterite" [project 19/p19_brief.json].

## 6. Finish vocabulary from the Goa / Konkan work

Use these as starting phrases, only for elements that are in the drawing.

- Roofs: Mangalore pantiles - flat interlocking clay tiles in straight courses, NOT Spanish
  barrel S-tiles [project 15]; weathered dark reddish-brown clay tile with teak rafter
  tails under deep eaves [late sweep]; flat light-grey membrane roof, no tiles, no pitch [project 18]; flat dark charcoal roof with stone-chip finish and slim fascia [project 16];
  razor-thin square-arrised chalk-white slab edge 250-350 mm [project 14].
- Walls: warm off-white lime plaster with subtle trowel texture [project 19]; smooth, evenly
  toned light-brown plaster with fine recessed panel joints (not blotchy tadelakt) [project 14/ai_materiality.py]; black hand-troweled lime plaster [project 18]; off-white
  board-formed fair-faced concrete [project 03]; ochre rammed earth, smooth and monolithic,
  NOT coursed brick [project 16]; red-ochre laterite stone [early sweep].
- Timber and openings: oiled teak joinery with visible grain; honey teak tongue-and-groove
  soffit; slim matte dark-bronze or black aluminium frames; clear low-iron glass reflecting sky
  and foliage, never mirror-black voids [project 14; project 18; project 19].
- Ground: large-format honed cream limestone or Kota stone slabs; fan-laid granite setts
  (calcada); pale compacted gravel lanes; oiled teak deck boards [project 14; project 19;
  early sweep].
- Water: clear turquoise over pale mosaic with ripples, refraction and caustics; muted aqua-grey
  for top-down plans, not bright turquoise [project 19; project 04].
- Planting: coconut and areca palms, mango, jackfruit, cashew, banyan, frangipani, heliconia,
  bougainvillea; dense post-monsoon lawn, never dry or patchy; Western Ghats or Konkan forest
  behind with haze in receding ridges [project 14; project 12; project 18].
- Neighbours outside the plot: modest, well-kept Goan houses, white or ochre walls, terracotta
  pantiles, half screened by palms - never grand, never derelict [project 14/render_new.py].

## 7. Light follows the drawing; new is not flat

Read the shadow direction already in the export and keep it: late-morning high sun for one
set, warm late-afternoon for another, sun behind the camera for a third [late sweep: project 19,
project 15, project 18]. Ask the user if the drawing has no shadows. Realism comes from
physics - hard directional sun, dark shadow cores, raking light on texture - not from the word
"photorealistic" [project 17/render_v3_photoreal.py]. Mist and haze may soften, never hide
the architecture [project 12/render_b8_view01_refmoods.py].

Keep AGE separate from PHYSICS. Told to remove all weathering, the model removed the surface as
well and the neighbours became flat white CG boxes: "New and clean is not the same as flat and
untextured" [project 17/render_v7_fix.py:9-11]. For a new build, remove age (stains, moss,
chipping) and keep physics (material grain, micro-relief, real light and shadow).

## 8. Drafting artefacts are named non-objects

Name each artefact in a caution and say what it becomes, or the model renders it:

- viewport UI (toolbar, ViewCube, cursor, minimap) - remove [project 02/
  render_super_estate_batch3.py];
- coloured axis or survey lines - not walls; a boundary wall was built along an orange axis line
  and "prompt wording did not stop it", so the tree erased the line from a copy of the input [project 19/clean_axis_lines.py] (render that copy with `--original <export>`);
- a magenta boundary strip - "a built wall, never a coloured or pink line" [project 19/
  p19_brief_av03_rev03.json];
- scale figures and scene labels on the ground - leave out; no people, no text [project 17];
- black edge outlines, texture seams, section-cut fill, hidden wireframes, sprite bleed -
  modelling debris, not objects [project 18/p18_brief.json; project 15];
- faceted grey placeholder plants - real plants of a named species, never rocks or vases [project 18/render_p18_tiled.py];
- a blurred Google Earth base - real terrain, kept where it is [project 14/render_new.py];
- topographic contour lines - not retaining walls or steps [project 10/render_style_transfer.py];
- white massing boxes - inside the estate, plain plastered buildings with no invented openings;
  outside, modest neighbours [project 14/render_new02.py];
- white or grey void - say what it is: sky above the horizon, land seen from above in an aerial
  [project 15/render_17_09_2026_1k.py].

## 9. Negatives for this frame only

Specific absent items beat a generic "no hallucination": "On this floor there is NO kitchen,
NO dining table for eight, NO sofa and NO extra bedroom" [project 04/
render_p04_flooring.py:232]; "NO second pool", "NO sports court of any kind" [project 03/render_p03_1k.py:204, 145]; "EXACTLY ONE pool, nothing built below it"
[project 19/p19_brief_av03_rev02.json]; "no water anywhere on the roof" for a flat garage
slab [project 14/fix_pass.py]; "no glazed roof over the courtyard - it is open to the sky"
[project 16/courtyard_fix.py]. Name only what a model is likely to invent here.

## 10. Solid walls, stated storeys, the roof as drawn

- "Walls are solid by default; glass is the exception": flat opaque fills read as glazing and
  slabs were tapered to knife edges [project 03/render_p03_1k.py].
- State the storey count of each block; single-storey blocks came back two-storey and prompts
  rarely fix height once wrong [project 19/prep_av04_rev04.py].
- Say opacity for doors: "a solid opaque door - you cannot see through it" [project 14/fix_pass.py].
- Copy unusual roofs plane by plane (planes, ridges, hips, valleys); the model re-solves them
  into a textbook shape [project 04/render_p04_flooring.py]. Flat roofs: "all
  roofs are flat - no tiles, no pitch, no terracotta" [project 18/p18_brief_rev02.json].
  If the user asks for a roof form the drawing does not show, point it out and ask first.

## 11. Depth of field, bounded

Unqualified "bokeh" or "cinematic depth of field" blurred whole facades and gave top-down plans
a tilt-shift toy look. Keep the building sharp edge to edge (deep focus, f/8-f/11); let only the
far background and nearest foreground soften; on aerials and plans, sharpness is uniform [project 16/render_p16_new2.py; project 12/render_master_layout_02.py; project 03].

## 12. What goes in the notes fields

The notes become the `USER NOTES` block - "the only permitted departures from the input beyond
material realism". Keep them to what the user asked for:

- `--materials`: the project material block (one finish per element class).
- `--lighting`: time of day and sun direction, matching the drawing's shadows.
- `--environment`: what surrounds the building (forest, sea, lawn, sky), scoped to the empty
  areas: client changes are allowed "ONLY inside the white void" [project 18/p18_brief.json].
- `--other`: anything else the user instructed, said once and tersely. A long correction text
  out-competed the tracing instruction and turned flat roofs hipped [project 16/
  render_p16_new_rev3.py].

## 13. By input type

**SketchUp / Revit eye-level export.** Treat the export as a tracing underlay; list each
plant's position, trunk and canopy size; keep foreground trees that hide the house; replace
CGI foliage with real plants of the same character [project 15/render_17_09_2026_1k.py;
project 14/render_p14.py]. Scale figures are entourage: leave them out. A drawn car or person
may be design (a drawn car became "one real white car" [project 04/
render_p04_flooring.py]); the fidelity brief says "No people, no vehicles", so ask
the user and put a keep instruction in `--other`. State the material of every flat fill.

**Aerial / drone export.** The commonest failure is the camera flying in. Lead with the framing
anchor and failure test, say the estate is small, keep the empty plots. Count buildings ("if
fewer than fifty villas, it is wrong") [project 12/render_hero_v2.py]. At 1K a villa there was
~15 px across "and the model answered by deleting the estate"; 2K costs the same as 1K [same
script, 55-61]. When key elements would be under about 20 px at 1K, suggest `--size 2K` and use
it only after the user agrees. A steep aerial whose pitch drops into a three-quarter view was
fixed by tiling, outside this skill; report it [project 15/fix_17_09_2026_v01_3_tiled.py].

**Elevation drawing.** Frontal, level camera, no perspective convergence; inventory openings
floor by floor, left to right; a portrait elevation stays portrait (the pad-and-crop path
holds the ratio) [Miscellaneous/render_facades.py].

**Hand sketch or marker plan.** Keep every outline and pathway exactly; say that paper texture,
pencil guide lines and handwritten numbers are removed - the one sketch pair still kept its zone
numbers [project 02/render_landscape.py]. The tree's fix for text was erasing it first [project 04]; render an erased copy with `--original <export>`.

**Coloured site or master plan, top-down.** Say it is an orthographic aerial photograph, the
drawing is the sole authority on counts and positions, the building count is fixed, shadows
give height, colours are less saturated than the drawing, and no tilt-shift blur [project 12/render_master_layout_02.py]. Default to lush post-monsoon surroundings [project 12/render_master_layout_02_rev2.py].

**A plan when the user wants a perspective.** Not possible here. Sent as a picture, a ground
floor plan was read as the building's shape and came back a single-storey bungalow [project 12/
render_b8_view01_birdseye_wide.py]; prompt-only camera moves gave a different villa each time -
"The AI has nothing to hold on to when the camera moves a long way" [project 12/
build_b8_massing.py]; an oblique hero from a top-down plan showed the wrong site [project 12/
hero_base.py]. Do not spend; ask for a 3D export of the view.

**Dense floor-plan sheets.** Render one panel (one floor) per call, never a whole sheet: whole
sheets came back with panels about 14% taller, invented labels and a redrawn house [project 04/render_p04_flooring.py; project 02 README]. Crop the panel first, tell
the model it is a tracing underlay with no text, give % layout checkpoints and exact furniture
counts, and add labels afterwards outside the render. Very dense furniture layouts failed
generatively in the tree; say so to the user before spending.

**Isolated model on a white void.** A big white void invites re-composition (a view that was 55%
white came back squared up) [project 18/render_p18_1k.py]. Wording alone did not fix it:
whole-frame passes failed on all five project 18 views; pre-filling the void (sky gradient above the
horizon, the model's own lawn colour below) plus a KNOWN FAILURE block registered one; the final
used tiling over a background plate [late sweep: project 18]. Warn the user; pre-fill a copy and
render it with `--original <export>`; if two 1K attempts still re-frame, stop and report.

## 14. A worked example

For `assets/test_sketch.png` (line elevation, 1.9:1), every count and position measured on
the drawing:

```json
{"elements": [
  "two-storey main block, centre-left, hipped roof with tile courses, 3 upper windows",
  "ground floor of main block: 2 windows and a central double door with 3 steps",
  "single-storey wing, right of centre, flat roof with a thin parapet, one 4-pane window",
  "open timber pergola on 3 posts, far left",
  "one coconut palm, far right (~87% of width), crown above the eaves but below the main ridge",
  "4 low shrub clumps along the plinth; pool coping line across the foreground"],
 "finishes": ["terracotta Mangalore pantile roof", "warm off-white lime plaster walls",
              "oiled teak doors and window frames", "honed cream limestone steps and coping"],
 "cautions": [
  "FRAMING: building spans 10-78% of width, ground line at 82% height; if it grows or sky is cut, the result has failed",
  "the wing is ONE storey with a FLAT roof - no tiles, no pitch on the wing",
  "no people, no cars, no text; nothing added in the empty sky or ground"]}
```
