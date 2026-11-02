# Prompts

Every prompt string the skill sends, copied from the code (this file is generated from the
vendored `_render_common.py` and from `render.py`, never retyped), the order in which they
are assembled, and real prompts produced by `render.py --prompt-only` on
`assets/test_sketch.png`. The model receives exactly one image part (the padded feed, JPEG)
followed by one text part (the prompt), with `responseModalities: ["TEXT", "IMAGE"]` and
`imageConfig: {imageSize, aspectRatio}`; there is no system instruction and no sampling
parameter.

## Contents
1. Constants, verbatim
2. Assembly order
3. The inventory block
4. Real assembled prompts
5. Deliberate differences from other tools in the tree

## 1. Constants, verbatim

### FIDELITY_PROMPT

From `scripts/_render_common.py (vendored)`. Base of every first-pass render. Not used by revise, patch or 4K.

```text
Re-render this architectural image as a real photograph while keeping the design identical.

GEOMETRY - NON-NEGOTIABLE:
- Maintain 100% accurate geometry, scale and ratio. Same camera position, lens angle, horizon and framing: no zoom, pan or crop.
- Every wall, roof plane, overhang, column, floor level, step, terrace, railing, pergola, window and door opening stays in exactly the same place, at exactly the same proportion, with the same mullion and glazing grid.
- The site stays as drawn: pool position, shape and size; paving patterns; driveways; boundary walls; planter bed layout; furniture positions.

NO HALLUCINATION:
- Do not invent, add, remove, move, resize or redesign any element unless you have been explicitly instructed to. No extra storeys, wings, openings, chimneys, canopies, steps, plants or furniture. Nothing may quietly disappear either.

MATERIALS BECOME REAL FINISHES:
- Replace placeholder materials with real photographed finishes: terracotta roof tiles with true clay colour variation and weathering; real trees, shrubs and lawns with individual leaves, real bark, natural asymmetry and see-through canopies; real pool water with ripples, refraction and caustics; real landscape and terrain with atmospheric depth; lime plaster with subtle tonal variation; timber with true grain; glass with real reflections of sky and foliage; stone with fine natural texture.

OUTPUT LOOK:
- The result must look like high-end DSLR architectural photography - an actual frame shot on a full-frame camera with a professional lens: true perspective, physically correct exposure, sharp focus, natural lighting, soft highlight roll-off, open readable shadows, accurate white balance, faint natural sensor grain.

ABSOLUTELY FORBIDDEN: any CGI / 3D-render / SketchUp / video-game look, illustration, cartoon, outlines, flat colour fills, plastic or over-smooth surfaces, repeating texture tiles, oversaturation, HDR halos. No people, no vehicles, no text, no logos, no watermarks, no signatures. Output ONE photograph only, matching the input framing.
```

### UPSCALE_PROMPT

From `scripts/_render_common.py (vendored)`. First block of the 4K prompt.

```text
4K QUALITY PASS on an already-approved image.
- Deliver sharp, detailed accuracy with no blur, no smudge, no soft mush and no painterly smearing anywhere in the frame.
- Every element must appear real and photorealistic when zoomed in: roof tiles read as individual tiles, foliage resolves into individual leaves, stone and plaster show true micro-texture, water shows real ripple and caustic detail, joinery and railings keep crisp straight edges.
- Preserve exact geometry and detail fidelity from the reference image: identical composition, framing, perspective, proportions, materials, colours, lighting and shadows. This is a resolution and sharpness pass only.
- Add nothing and remove nothing. Do not restyle, recolour, relight or redesign any part of the approved image.
```

### USER NOTES wrapper

From `render.py build_prompt (from the local app)`. Starts with 2 newline characters (a blank line before it). Ends with one newline character. Added after FIDELITY_PROMPT when the render has notes; the notes follow directly.

```text
USER NOTES - explicit instructions for this render. Apply them exactly and treat them as the only permitted departures from the input beyond material realism:
```

### SKETCH ELEMENT INVENTORY header

From `render.py _brief_text (from the hosted version)`. Starts with 2 newline characters (a blank line before it). Ends with one newline character. Opens the brief block; the elements follow as '- ' lines, then 'FINISHES TO USE:' and 'TAKE SPECIAL CARE:' lists when present.

```text
SKETCH ELEMENT INVENTORY (an automatic analysis of the input; treat it as a checklist: every listed element must appear, in the same place and proportion, and nothing else may be added):
```

### CANVAS_NOTE

From `render.py (from the local app)`. Starts with 2 newline characters (a blank line before it). Added to any pass whose feed was edge-extended; {where} is 'left and right' or 'top and bottom'.

```text
CANVAS: the attached image has been extended with a thin {where} band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.
```

### FINAL AND OVERRIDING framing tail

From `render.py build_prompt`. Starts with 2 newline characters (a blank line before it). Always the last text of a first-pass render.

```text
FINAL AND OVERRIDING - FRAMING: same camera, same framing, same geometry as the input, nothing added and nothing removed. Output ONE photograph.
```

### REVISE_HEADER

From `render.py (from the local app)`. Opens every revision; a blank line and the change notes follow.

```text
EDIT THIS PHOTOGRAPH. Its framing is already correct; keep it high-end DSLR architectural photography. Keep the camera, framing, every wall, opening, slab, roof, pool, deck, plant position, the light and the colour grade identical, and add or remove nothing, EXCEPT for these changes:
```

### Revise placeholder

From `render.py build_prompt`. Unreachable in practice: revise refuses empty notes.

```text
(no changes given - reproduce the image)
```

### LOCKED_FINISHES (the local app's long version)

From `render.py (from the local app)`. Second block of the 4K prompt.

```text
LOCKED FINISHES: every material, colour, plant, texture and light in the attached approved image is final. Reproduce them exactly at higher resolution. Do not substitute any finish for another, however typical the alternative may be.
```

### UPSCALE_LOOK

From `render.py (from the local app)`. Third block of the 4K prompt; replaces FIDELITY_PROMPT's materials and look paragraphs.

```text
OUTPUT LOOK: high-end DSLR architectural photography - true perspective, physically correct exposure, sharp focus, natural lighting, accurate white balance, faint natural sensor grain. No CGI / 3D-render look, no illustration, no text, no logos, no people.
```

### 4K notes reference

From `render.py build_prompt`. Starts with 2 newline characters (a blank line before it). Ends with one newline character. Added to the 4K prompt when the approved pass had notes; those notes follow.

```text
For reference, the approved image was made with these notes:
```

### Revise / 4K tail

From `render.py build_prompt`. Starts with 2 newline characters (a blank line before it). Always the last text of a revise or 4K prompt.

```text
Output ONE photograph with exactly the same framing.
```

### 4K later-changes line

From `render.py upscale_notes`. 4K only, when the approved image is a revision or patch: follows the first render's notes inside the 4K notes reference; each later revise / patch note follows as a '- ' line.

```text
Later changes, already made in the approved image (do not apply them again):
```

### Patch HEADER

From `render.py (from project 18/patch_p18_1k.py)`. Opens every patch prompt; a blank line and the change follow.

```text
EDIT THIS PHOTOGRAPH. It is a close-up crop of a larger architectural photograph and will be pasted back into it, so keep the camera, framing, scale, light and colour grade identical. The change below is required and must be clearly visible; everything else in the crop stays exactly as it is. Make this change:
```

### Patch TAIL

From `render.py (from project 18/patch_p18_1k.py)`. Starts with 2 newline characters (a blank line before it). Always the last text of a patch prompt.

```text
Output ONE photograph with exactly the same framing as this crop.
```

### TERRACOTTA clause

From `render.py (from project 18/render_p18_1k.py)`. Ends with one space. The exact text --no-terracotta-example removes from FIDELITY_PROMPT.

```text
terracotta roof tiles with true clay colour variation and weathering; 
```

## 2. Assembly order

**Render (first pass, `kind=render`):**

1. `FIDELITY_PROMPT` (minus the TERRACOTTA clause with `--no-terracotta-example`)
2. if notes: USER NOTES wrapper + the notes (free text, or the four fields as
   `Materials: ...` / `Lighting: ...` / `Environment: ...` / `Other: ...` lines, empty ones dropped)
3. if `--brief`: the SKETCH ELEMENT INVENTORY block (section 3)
4. if the feed was padded: `CANVAS_NOTE` with `left and right` or `top and bottom`
5. the FINAL AND OVERRIDING framing tail

**Revise (`kind=revise`):** `REVISE_HEADER` + blank line + the change notes; `CANVAS_NOTE` if padded;
the revise / 4K tail. The image sent is the current render (the image being revised).

**Patch (`kind=patch`):** Patch HEADER + blank line + the change; `CANVAS_NOTE` if the crop was padded;
Patch TAIL. The image sent is the padded crop of the box, not the whole frame. HEADER and TAIL are
`project 18/patch_p18_1k.py`'s; the canvas note is the local app's (project 18's own adds a sentence
saying brief percentages refer to the area inside the band, which a patch note has none of).

**4K (`kind=4k`):** `UPSCALE_PROMPT` + blank line + `LOCKED_FINISHES` + blank line + `UPSCALE_LOOK`;
if there are notes, the 4K notes reference + the notes (see below); `CANVAS_NOTE` if padded; the
revise / 4K tail. The image sent is the approved file, padded; `imageSize` is `4K`.

The 4K notes: for an approved first render, that pass's own notes (as the local app). For an
approved revision or patch, the notes of the render that started its lineage, then the 4K
later-changes line and each revise / patch note as a `- ` line. The local app carried only the approved
pass's own note - for a revision an imperative edit such as "add a second lounger" that a
resolution pass could apply again - and lost the render's material notes. Read the 4K prompt with
`--prompt-only` before a live 4K, and check on the 4K sheet that nothing was doubled.

## 3. The inventory block

`--brief` JSON `{"elements": [...], "finishes": [...], "cautions": [...]}` becomes, after the notes:

```text
SKETCH ELEMENT INVENTORY (an automatic analysis of the input; treat it as a checklist: every listed element must appear, in the same place and proportion, and nothing else may be added):
- <element 1>
- <element 2>
FINISHES TO USE:
- <finish 1>
TAKE SPECIAL CARE:
- <caution 1>
```

Control characters in items become spaces; limits are 30 elements x 160 characters, 15 finishes x
120, 10 cautions x 160, and 3000 characters for the block (the script refuses a brief that would be
cut). With no elements the block is omitted.

## 4. Real assembled prompts

Produced on 9 Oct 2026 by the commands shown (the revise, patch and 4K examples run on a dry-run
render of the test sketch; prompt-only runs send nothing and read no key).

### Render: notes in four fields + a brief, canvas padded top and bottom

```
python scripts/render.py render assets/test_sketch.png --name "Test Villa" --out "<scratch>/03 Output" --materials "terracotta Mangalore pantile roof, warm off-white lime plaster, teak joinery" --lighting "warm late-afternoon sun from the left, soft long shadows" --environment "coconut palms and a clear sky behind, mown lawn in front" --brief test_villa_brief.json --prompt-only
```

```text
Re-render this architectural image as a real photograph while keeping the design identical.

GEOMETRY - NON-NEGOTIABLE:
- Maintain 100% accurate geometry, scale and ratio. Same camera position, lens angle, horizon and framing: no zoom, pan or crop.
- Every wall, roof plane, overhang, column, floor level, step, terrace, railing, pergola, window and door opening stays in exactly the same place, at exactly the same proportion, with the same mullion and glazing grid.
- The site stays as drawn: pool position, shape and size; paving patterns; driveways; boundary walls; planter bed layout; furniture positions.

NO HALLUCINATION:
- Do not invent, add, remove, move, resize or redesign any element unless you have been explicitly instructed to. No extra storeys, wings, openings, chimneys, canopies, steps, plants or furniture. Nothing may quietly disappear either.

MATERIALS BECOME REAL FINISHES:
- Replace placeholder materials with real photographed finishes: terracotta roof tiles with true clay colour variation and weathering; real trees, shrubs and lawns with individual leaves, real bark, natural asymmetry and see-through canopies; real pool water with ripples, refraction and caustics; real landscape and terrain with atmospheric depth; lime plaster with subtle tonal variation; timber with true grain; glass with real reflections of sky and foliage; stone with fine natural texture.

OUTPUT LOOK:
- The result must look like high-end DSLR architectural photography - an actual frame shot on a full-frame camera with a professional lens: true perspective, physically correct exposure, sharp focus, natural lighting, soft highlight roll-off, open readable shadows, accurate white balance, faint natural sensor grain.

ABSOLUTELY FORBIDDEN: any CGI / 3D-render / SketchUp / video-game look, illustration, cartoon, outlines, flat colour fills, plastic or over-smooth surfaces, repeating texture tiles, oversaturation, HDR halos. No people, no vehicles, no text, no logos, no watermarks, no signatures. Output ONE photograph only, matching the input framing.

USER NOTES - explicit instructions for this render. Apply them exactly and treat them as the only permitted departures from the input beyond material realism:
Materials: terracotta Mangalore pantile roof, warm off-white lime plaster, teak joinery
Lighting: warm late-afternoon sun from the left, soft long shadows
Environment: coconut palms and a clear sky behind, mown lawn in front

SKETCH ELEMENT INVENTORY (an automatic analysis of the input; treat it as a checklist: every listed element must appear, in the same place and proportion, and nothing else may be added):
- two-storey main block, centre-left, hipped roof with tile courses, 3 upper windows
- ground floor of main block: 2 windows and a central double door with 3 steps
- single-storey wing, right of centre, flat roof with a thin parapet, one 4-pane window
- open timber pergola on 3 posts, far left
- one coconut palm, far right (~87% of width), crown above the eaves but below the main ridge
- 4 low shrub clumps along the plinth; pool coping line across the foreground
FINISHES TO USE:
- terracotta Mangalore pantile roof
- warm off-white lime plaster walls
- oiled teak doors and window frames
- honed cream limestone steps and coping
TAKE SPECIAL CARE:
- FRAMING: building spans 10-78% of width, ground line at 82% height; if it grows or sky is cut, the result has failed
- the wing is ONE storey with a FLAT roof - no tiles, no pitch on the wing
- no people, no cars, no text; nothing added in the empty sky or ground

CANVAS: the attached image has been extended with a thin top and bottom band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.

FINAL AND OVERRIDING - FRAMING: same camera, same framing, same geometry as the input, nothing added and nothing removed. Output ONE photograph.
```

### Revise: one change on the current render

```
python scripts/render.py revise "<scratch>/03 Output/Test Villa_1K.png" --notes "make the flat roof of the right-hand wing a planted green roof" --prompt-only
```

```text
EDIT THIS PHOTOGRAPH. Its framing is already correct; keep it high-end DSLR architectural photography. Keep the camera, framing, every wall, opening, slab, roof, pool, deck, plant position, the light and the colour grade identical, and add or remove nothing, EXCEPT for these changes:

make the flat roof of the right-hand wing a planted green roof

CANVAS: the attached image has been extended with a thin top and bottom band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.

Output ONE photograph with exactly the same framing.
```

### Patch: one region, box 0.55,0.30,0.85,0.80 (the crop is padded left and right)

```
python scripts/render.py patch "<scratch>/03 Output/Test Villa_1K.png" --box 0.55,0.30,0.85,0.80 --notes "the four-pane window of the single-storey wing becomes a pair of solid teak doors of the same width" --prompt-only
```

```text
EDIT THIS PHOTOGRAPH. It is a close-up crop of a larger architectural photograph and will be pasted back into it, so keep the camera, framing, scale, light and colour grade identical. The change below is required and must be clearly visible; everything else in the crop stays exactly as it is. Make this change:

the four-pane window of the single-storey wing becomes a pair of solid teak doors of the same width

CANVAS: the attached image has been extended with a thin left and right band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.

Output ONE photograph with exactly the same framing as this crop.
```

### 4K of an approved first render (its own notes are carried for reference)

```
python scripts/render.py upscale "<scratch>/03 Output/Test Villa_1K.png" --prompt-only    (live: --confirmed)
```

```text
4K QUALITY PASS on an already-approved image.
- Deliver sharp, detailed accuracy with no blur, no smudge, no soft mush and no painterly smearing anywhere in the frame.
- Every element must appear real and photorealistic when zoomed in: roof tiles read as individual tiles, foliage resolves into individual leaves, stone and plaster show true micro-texture, water shows real ripple and caustic detail, joinery and railings keep crisp straight edges.
- Preserve exact geometry and detail fidelity from the reference image: identical composition, framing, perspective, proportions, materials, colours, lighting and shadows. This is a resolution and sharpness pass only.
- Add nothing and remove nothing. Do not restyle, recolour, relight or redesign any part of the approved image.

LOCKED FINISHES: every material, colour, plant, texture and light in the attached approved image is final. Reproduce them exactly at higher resolution. Do not substitute any finish for another, however typical the alternative may be.

OUTPUT LOOK: high-end DSLR architectural photography - true perspective, physically correct exposure, sharp focus, natural lighting, accurate white balance, faint natural sensor grain. No CGI / 3D-render look, no illustration, no text, no logos, no people.

For reference, the approved image was made with these notes:
Materials: terracotta Mangalore pantile roof, warm off-white lime plaster, teak joinery
Lighting: warm late-afternoon sun from the left, soft long shadows
Environment: coconut palms and a clear sky behind, mown lawn in front

CANVAS: the attached image has been extended with a thin top and bottom band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.

Output ONE photograph with exactly the same framing.
```

### 4K of an approved revision (the render's notes, then the revision marked as already made)

```
python scripts/render.py upscale "<scratch>/03 Output/Test Villa_1K_rev02.png" --prompt-only    (after a revise that added a lounger)
```

```text
4K QUALITY PASS on an already-approved image.
- Deliver sharp, detailed accuracy with no blur, no smudge, no soft mush and no painterly smearing anywhere in the frame.
- Every element must appear real and photorealistic when zoomed in: roof tiles read as individual tiles, foliage resolves into individual leaves, stone and plaster show true micro-texture, water shows real ripple and caustic detail, joinery and railings keep crisp straight edges.
- Preserve exact geometry and detail fidelity from the reference image: identical composition, framing, perspective, proportions, materials, colours, lighting and shadows. This is a resolution and sharpness pass only.
- Add nothing and remove nothing. Do not restyle, recolour, relight or redesign any part of the approved image.

LOCKED FINISHES: every material, colour, plant, texture and light in the attached approved image is final. Reproduce them exactly at higher resolution. Do not substitute any finish for another, however typical the alternative may be.

OUTPUT LOOK: high-end DSLR architectural photography - true perspective, physically correct exposure, sharp focus, natural lighting, accurate white balance, faint natural sensor grain. No CGI / 3D-render look, no illustration, no text, no logos, no people.

For reference, the approved image was made with these notes:
Materials: terracotta Mangalore pantile roof, warm off-white lime plaster, teak joinery
Lighting: warm late-afternoon sun from the left, soft long shadows
Environment: coconut palms and a clear sky behind, mown lawn in front
Later changes, already made in the approved image (do not apply them again):
- add a second teak sun lounger beside the existing one on the pool deck

CANVAS: the attached image has been extended with a thin top and bottom band of smeared, stretched edge pixels so it fits the output format. That band is filler, not design. Keep the whole scene exactly where it sits in the canvas at exactly its size - do not re-centre, zoom or crop to use the band - and simply continue the surroundings (sky, ground) into it.

Output ONE photograph with exactly the same framing.
```

## 5. Deliberate differences from other tools in the tree

- **The 4K pass omits `FIDELITY_PROMPT`.** Its materials paragraph names example finishes
  (terracotta tiles, lawns); on a job whose approved scheme differs it can undo the approval
  during the resolution pass. The approved image is the materials reference, locked by
  `LOCKED_FINISHES`, and `UPSCALE_LOOK` replaces the look paragraph. This is the local app's 4K
  prompt.
- **`upscale_to_4k.py` in the tree is not used by the skill.** Its built-in prompt is
  `FIDELITY_PROMPT + "\n\n" + UPSCALE_PROMPT` (terracotta paragraph included, no locked finishes),
  and it sends the approved file without padding or a forced aspect ratio.
- **`LOCKED_FINISHES` is the local app's long version**, ending "however typical the alternative may be.";
  the hosted version's copy drops that clause.
- **The inventory block comes from the hosted version**, where Claude's API wrote it automatically; here you
  write it by looking at the drawing. The local app has no inventory block; otherwise the render prompt is
  byte-identical to the local app's and the hosted version's.
- **Revise exists in the local app and the estate scripts; patch only in the project 18 and 19
  scripts.** The hosted version re-renders from the sketch instead.
- **The 4K notes for an approved revision or patch** differ from the local app's (section 2); for an approved
  first render they are identical.
