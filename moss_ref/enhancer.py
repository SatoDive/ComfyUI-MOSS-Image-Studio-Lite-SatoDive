"""MOSS Prompt Enhancer: plain words -> an official MOSS-Image prompt (caption or Layout), written by the model's own
text encoder (Qwen3.5-9B is a full chat / vision LLM).

The rules follow the two official guides:
- OpenMOSS `skills/moss-image-prompt-enhancer` (Apache-2.0): caption vs Layout choice, pixel-xyxy Layout drafts and
  the deterministic compile to `abs_centralized` / `yxyx` (ported 1:1 in `compile_layout`, plus repairs).
- Comfy-Org's MOSS-Image template prompt upsampler: the eight facets, text rules, reference-picture rules, lengths.

The LLM only writes; the pack parses, repairs and compiles deterministically (no retries - each call is slow).
"""

import json
import math
import re
import time

MODES = ["auto (official choice)", "caption", "layout"]
DETAIL = ["official (220-500 words)", "short (80-150 words)", "minimal (as short as my brief)"]

LENGTH_RULES = {
    DETAIL[0]: "Length: aim for 220 to 320 words for a single-subject scene and 320 to 500 words for posters, cards, "
               "multi-subject scenes and text-heavy layouts; never fewer than 200 words. Do not pad: if you fall short, "
               "add missing visible detail from the eight facets instead of repeating yourself.",
    DETAIL[1]: "Length: 80 to 150 words. Keep every detail the user gave; add only the most important visible detail.",
    DETAIL[2]: "Length: keep it as short as the user's brief allows - a minimalist brief stays minimalist. Only make it "
               "concrete and visual; add nothing decorative.",
}
MAX_TOKENS = {DETAIL[0]: 900, DETAIL[1]: 360, DETAIL[2]: 260}
LAYOUT_EXTRA_TOKENS = 700

SYSTEM_PROMPT = """You are the prompt writer for MOSS-Image, an image generation model. The user sends a rough idea in any language, sometimes with exact text to render or a wish for a poster or layout. You turn it into the prompt the image model reads.

GENERAL RULES
- Preserve everything the user specifies: subjects and their number, identity, action, relationships, clothing, style, medium, era, composition, palette, exclusions, and every piece of wording they want visible. Add only plausible visible detail the user left open. Never add new people, plot or dialogue, never change relationships, never invent real product specifications, prices, certifications, event details, real people's names or titles.
- Default to English prose (or the output language the user asks for). Visible text stays verbatim in its original language, with its punctuation, capitalisation and requested line breaks. A quoted sentence in an instruction is not always text to render: tell visible wording apart from references and constraints.
- Describe only what is visible: no tool steps, generation parameters, sizes, ratios, resolutions, pixel counts or coordinate arithmetic inside descriptions. No quality tag soup ("masterpiece, 8k, best quality").
- The prompt always describes the finished picture as it looks, never an instruction to an editor: never write "replace", "remove", "keep", "preserve", "unchanged", "the original", "the reference image", "the source" or "same as".

THE EIGHT FACETS (cover a facet only when the scene has content for it; never repeat one to pad)
1. Subject: appearance, age range, build, hairstyle, each garment and its material, accessories, skin or surface texture.
2. Action: body orientation, limb positions, weight, what the hands do, gaze, expression - a pose that holds in one frame.
3. Space: foreground, midground, background, relative positions, occlusion, distances, what sits at the frame edges.
4. Setting: architecture, interior, furniture, props, signs of use, details of time and place (signage, windows, weather).
5. Framing: shot size, camera height, viewing angle, perspective, where the subject sits in the frame, empty space.
6. Light: direction and height of the key light, hardness, colour temperature, practical sources, how light falls on skin, fabric, glass, metal, wet ground.
7. Tone: palette, contrast, grain, medium (photograph, film, print, 3D render, painting, anime illustration...), texture, atmosphere.
8. Text: the most common failure point - see TEXT RULES.

TEXT RULES
- Keep the user's wording verbatim in its original language and write the full string inside double quotes. Never rewrite, translate, shorten, or write the same copy twice.
- For each text block state: exact content, carrier (sign, poster, label, screen, packaging...), position and relative size, typeface style and colour, legibility.
- When the scene clearly needs text but the user gave none (signs, menus, covers, interfaces), write short, fitting, specific wording verbatim. Never write placeholders like "headline here".
- For precise line breaks, put each line in its own quotes or on its own line.

WRITING STYLE
- Flowing natural language ordered by space or by the viewer's eye, in two to four paragraphs. Start with the medium and the subject ("Studio photograph of ...", "Anime-style digital illustration of ...", "Minimalist poster of ..."), never with a verb.
- Every sentence adds new visible information.
{length}

{deliverable}
"""

CAPTION_TASK = """WHAT TO RETURN
Return ONLY the caption text: no title, no preamble, no explanation, no alternatives, no code fences, no JSON."""

LAYOUT_TASK = """WHAT TO RETURN: A LAYOUT DRAFT
Return ONLY one JSON object (no code fences, no comments, nothing before or after it), in this exact schema:
{{"width": {w}, "height": {h}, "bbox_coord_space": "abs", "bbox_format": "xyxy",
 "summary": {{"meta": ["<medium or genre tags>"], "canvas": "single", "caption": "<global description of the whole image: medium, scene, style, palette, light>"}},
 "items": [ {{"label": "object" | "character" | "text", "caption": "<visible appearance of this item; for text: typeface, colour, carrier>", "text": "<exact visible characters - text items only>", "bbox": [x_min, y_min, x_max, y_max]}} ]}}
- The canvas is {w} x {h} pixels. Boxes are ACTUAL PIXELS from the top-left corner: x from 0 to {w}, y from 0 to {h}, x_min < x_max, y_min < y_max. Do not normalise, centre or reorder them.
- Use one box per coherent visible unit (a person = "character", a thing or a background area = "object", a block of words = "text"). Put background items first and foreground items last. Overlap and occlusion are fine. A box is a placement, never a border or panel to draw.
- Text items carry the exact visible characters in "text" (a line break is \\n inside the string). Check that the text can fit its box at that size: a long sentence needs a wide, tall box; a short title can be big.
- summary.caption holds the global treatment; item captions describe only their own item; no coordinates or JSON talk inside any caption. Escape double quotes inside strings as \\".
Example for a 1536 x 1024 canvas:
{{"width": 1536, "height": 1024, "bbox_coord_space": "abs", "bbox_format": "xyxy", "summary": {{"meta": ["product campaign", "studio photography"], "canvas": "single", "caption": "A warm studio campaign for a handmade ceramic cup, with an ivory backdrop, soft side lighting and restrained dark-green typography, calm composition and tactile ceramic texture."}}, "items": [{{"label": "object", "caption": "An ivory ceramic cup with a rounded handle, fine speckled glaze and a soft contact shadow, photographed at a three-quarter angle.", "bbox": [176, 224, 800, 864]}}, {{"label": "text", "caption": "Large dark-green title in crisp, moderately heavy lettering, generous spacing, no backing panel.", "text": "Slow mornings", "bbox": [928, 272, 1408, 448]}}, {{"label": "text", "caption": "Smaller dark-green supporting copy on two lines, comfortably legible.", "text": "Handmade cups\\nfor quiet days", "bbox": [928, 512, 1376, 656]}}]}}"""

AUTO_TASK = """CHOOSE THE DELIVERABLE
If the user explicitly asks for a caption or a layout, give that. Otherwise write a CAPTION for ordinary scenes, photographs and illustrations, and a LAYOUT only when specific text placement, a poster, several panels or controlled object positions clearly benefit from boxes. A detailed image does not automatically need a layout.

If you choose a caption: return ONLY the caption text (no title, no preamble, no JSON).
If you choose a layout: return ONLY the JSON object described below, starting with {{.

""" + LAYOUT_TASK


def system_prompt(mode, detail, width, height):
    if mode == MODES[1]:
        task = CAPTION_TASK
    elif mode == MODES[2]:
        task = LAYOUT_TASK.format(w=width, h=height)
    else:
        task = AUTO_TASK.format(w=width, h=height)
    return SYSTEM_PROMPT.format(length=LENGTH_RULES.get(detail, LENGTH_RULES[DETAIL[0]]), deliverable=task)


def picture_note(n):
    if not n:
        return ""
    if n == 1:
        return "\n\n(One picture is attached: it is \"image 1\".)"
    return f"\n\n({n} pictures are attached, in order: \"image 1\" to \"image {n}\".)"


def user_message(text, has_image):
    n = has_image if isinstance(has_image, int) and not isinstance(has_image, bool) else int(bool(has_image))
    return "My idea:\n" + text.strip() + picture_note(n)


# ---------------------------------------------------------------------------------------------- answer parsing
THINK_RE = re.compile(r"<think>.*?</think>", re.S)
FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
PREFIX_RE = re.compile(r"^\s*(?:\*\*)?(?:caption|prompt|final prompt|here is (?:the|your) (?:caption|prompt))(?:\*\*)?\s*:\s*", re.I)


def clean_caption(answer):
    s = THINK_RE.sub("", answer).strip()
    s = s.split("</think>")[-1].strip()
    s = FENCE_RE.sub("", s).strip()
    s = PREFIX_RE.sub("", s).strip()
    if s.startswith("{") and s.endswith("}"):        # a caption sent as {"caption": "..."}
        try:
            d = json.loads(s)
            if isinstance(d, dict) and isinstance(d.get("caption"), str) and "items" not in d:
                return d["caption"].strip()
        except ValueError:
            pass
    return s


def find_json(answer):
    """-> dict or None: the first JSON object in the answer (code fences / chatter around it tolerated)."""
    s = THINK_RE.sub("", answer).split("</think>")[-1]
    start = s.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    d = json.loads(s[start:i + 1])
                    return d if isinstance(d, dict) else None
                except ValueError:
                    return None
    return None


# ---------------------------------------------------------------------------------------------- layout compile
LABELS = {"object": "object", "obj": "object", "thing": "object", "background": "object", "prop": "object",
          "character": "character", "person": "character", "human": "character", "people": "character",
          "subject": "character", "text": "text", "title": "text", "caption": "text", "headline": "text"}
SUMMARY_KEYS = ("caption", "meta", "canvas", "palette")
ITEM_KEYS = ("label", "caption", "bbox", "text", "tags", "palette")


def centered_box(box, width, height):
    """Official compile (skills/moss-image-prompt-enhancer/scripts/compile_prompt.py): enclose fractional pixel edges,
    then subtract the centre -> [y1, x1, y2, x2]."""
    x1, y1, x2, y2 = box
    return [math.floor(round(y1, 9)) - height // 2, math.floor(round(x1, 9)) - width // 2,
            math.ceil(round(y2, 9)) - height // 2, math.ceil(round(x2, 9)) - width // 2]


def _strings(v):
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def repair_layout(draft, width, height):
    """-> (clean draft in the official draft schema, notes). Repairs only what is sure; drops what cannot be placed."""
    notes = []
    summary = draft.get("summary") if isinstance(draft.get("summary"), dict) else {}
    if not isinstance(draft.get("summary"), dict) and isinstance(draft.get("summary"), str):
        summary = {"caption": draft["summary"]}
    caption = str(summary.get("caption") or draft.get("caption") or "").strip()
    out_summary = {"caption": caption}
    for k in ("meta", "palette"):
        s = _strings(summary.get(k, []))
        if s:
            out_summary[k] = s
    if summary.get("canvas") in ("single", "multi_panel", "collage"):
        out_summary["canvas"] = summary["canvas"]
    dropped = sorted(set(summary) - set(SUMMARY_KEYS))
    if dropped:
        notes.append(f"summary: dropped unknown fields {dropped}")

    # the LLM may have drawn on another canvas: scale its boxes onto ours
    dw, dh = draft.get("width"), draft.get("height")
    sx = width / dw if isinstance(dw, (int, float)) and dw > 0 else 1.0
    sy = height / dh if isinstance(dh, (int, float)) and dh > 0 else 1.0
    if (sx, sy) != (1.0, 1.0):
        notes.append(f"boxes drawn on {dw}x{dh}, scaled to {width}x{height}")
    fmt = str(draft.get("bbox_format", "xyxy")).lower()

    items = []
    raw_items = draft.get("items") if isinstance(draft.get("items"), list) else []
    for i, it in enumerate(raw_items):
        where = f"item {i + 1}"
        if not isinstance(it, dict):
            notes.append(f"{where}: not an object, dropped")
            continue
        label = LABELS.get(str(it.get("label", "object")).strip().lower(), "object")
        if label != str(it.get("label", "")).strip().lower():
            notes.append(f"{where}: label {it.get('label')!r} -> {label}")
        text = it.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if label == "text" and not text:
            label = "object"
            notes.append(f"{where}: text item without text -> object")
        cap = str(it.get("caption") or it.get("description") or it.get("desc") or "").strip()
        if not cap:
            cap = (f"Lettering reading \"{text}\"" if text else "")
            if not cap:
                notes.append(f"{where}: no caption, dropped")
                continue
        box = it.get("bbox")
        try:
            box = [float(v) for v in box]
            assert len(box) == 4 and all(math.isfinite(v) for v in box)
        except Exception:
            notes.append(f"{where}: bbox {box!r} unreadable, dropped")
            continue
        if fmt == "xywh":
            box = [box[0], box[1], box[0] + box[2], box[1] + box[3]]
        elif fmt == "yxyx":
            box = [box[1], box[0], box[3], box[2]]
        box = [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]
        if box[0] > box[2] or box[1] > box[3]:
            box = [min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])]
            notes.append(f"{where}: inverted box corrected")
        clamped = [min(max(box[0], 0), width), min(max(box[1], 0), height), min(max(box[2], 0), width), min(max(box[3], 0), height)]
        if clamped != box:
            notes.append(f"{where}: box clipped to the canvas")
        if clamped[2] - clamped[0] < 1 or clamped[3] - clamped[1] < 1:
            notes.append(f"{where}: box outside the canvas or empty, dropped")
            continue
        item = {"label": label, "caption": cap}
        if text:
            item["text"] = text
        for k in ("tags", "palette"):
            s = _strings(it.get(k, []))
            if s:
                item[k] = s
        item["bbox"] = [round(v, 3) for v in clamped]
        extra = sorted(set(it) - set(ITEM_KEYS) - {"description", "desc"})
        if extra:
            notes.append(f"{where}: dropped unknown fields {extra}")
        items.append(item)
    return {"width": width, "height": height, "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": out_summary, "items": items}, notes


def compile_layout(draft, width, height):
    """Clean pixel draft -> the one-line MOSS Layout prompt (official key order and conversion)."""
    items = []
    for it in draft["items"]:
        items.append({k: (centered_box(v, width, height) if k == "bbox" else v) for k, v in it.items()})
    result = {"summary": draft["summary"], "items": items, "bbox_coord_space": "abs_centralized", "bbox_format": "yxyx"}
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def to_prompt(answer, mode, width, height):
    """-> (prompt, kind, notes). Never raises: an unreadable layout falls back to a caption."""
    want_layout = mode == MODES[2]
    looks_json = THINK_RE.sub("", answer).split("</think>")[-1].lstrip().lstrip("`").lstrip("json").lstrip().startswith("{")
    if want_layout or (mode == MODES[0] and looks_json):
        draft = find_json(answer)
        if draft is not None and ("items" in draft or "summary" in draft):
            clean, notes = repair_layout(draft, width, height)
            if clean["items"] and clean["summary"]["caption"]:
                return compile_layout(clean, width, height), "layout", notes
            if clean["summary"]["caption"]:
                return clean["summary"]["caption"], "caption", notes + ["no usable boxes: used the summary caption"]
        if mode == MODES[0] or not looks_json:
            cap = clean_caption(answer)
            if cap and not cap.startswith("{"):
                return cap, "caption", ["the answer was not a layout: used it as a caption"] if want_layout else []
        return "", "failed", ["the layout answer could not be read"]
    return clean_caption(answer), "caption", []


# ---------------------------------------------------------------------------------------------- the LLM call
def generate(clip, system, user, image=None, temperature=0.4, seed=0, max_length=900):
    """Same path as ComfyUI's Generate Text node (Qwen3.5 chat template, thinking off, MTP when available).
    image: None, one IMAGE, or a list of [1, H, W, 3] pictures (each read by the vision tower, in order)."""
    if isinstance(image, (list, tuple)):
        tokens = clip.tokenize(user, images=list(image), min_length=1, thinking=False, system_prompt=system)
    else:
        tokens = clip.tokenize(user, image=image, min_length=1, thinking=False, system_prompt=system)
    ids = clip.generate(tokens, do_sample=temperature > 0, max_length=max_length, temperature=max(temperature, 0.01),
                        top_k=64, top_p=0.95, min_p=0.05, repetition_penalty=1.05, seed=seed, mtp=True)
    return clip.decode(ids)


def enhance(clip, text, mode, detail, creativity, variation, width, height, image=None, generate_fn=None):
    """-> (prompt, report). text is returned unchanged when the answer is unusable (the render never stops)."""
    if not text.strip():
        return text, "Enhancer ON but the text is empty - nothing to rewrite."
    t0 = time.time()
    system = system_prompt(mode, detail, width, height)
    max_length = MAX_TOKENS.get(detail, 900) + (LAYOUT_EXTRA_TOKENS if mode != MODES[1] else 0)
    temperature = 0.2 + 0.8 * float(creativity)
    n_pics = len(image) if isinstance(image, (list, tuple)) else int(image is not None)
    try:
        answer = (generate_fn or generate)(clip, system, user_message(text, n_pics), image,
                                           temperature, int(variation), max_length)
    except Exception as error:  # the main job never stops on the helper
        return text, f"Enhancer failed ({type(error).__name__}: {error}) - your own text was used."
    prompt, kind, notes = to_prompt(answer, mode, width, height)
    secs = time.time() - t0
    if kind == "failed" or not prompt.strip():
        return text, (f"Enhancer answer unusable ({'; '.join(notes) or 'empty'}) - your own text was used. "
                      f"Raw answer: {answer[:400]}")
    words = len(prompt.split()) if kind == "caption" else len(json.loads(prompt)["items"])
    head = (f"Enhancer ON: {kind}, {words} {'words' if kind == 'caption' else 'boxes'}"
            f"{f' for {width}x{height} (use the same size in the render)' if kind == 'layout' else ''}, "
            f"{secs:.1f}s, temperature {temperature:.2f}, variation {variation}")
    return prompt, head + ("\nRepairs: " + "; ".join(notes) if notes else "")


# ---------------------------------------------------------------------------------------------- per-box rewriting
# With layout boxes the enhancer rewrites EACH box's own description (and the global prompt) separately: the boxes'
# places, types, exact words and pictures never change, and each box's strict strength sets how free it is.
FREEDOM = (  # (strict at least, label, rule for the LLM)
    (0.99, "locked", "copy it exactly, character for character"),
    (0.66, "low", "keep the user's words; only fix grammar and make vague words concrete; add nothing new"),
    (0.33, "medium", "keep everything the user wrote; add only a little plausible visible detail (material, colour, light)"),
    (0.0, "high", "keep everything the user wrote and describe it richly with visible detail (appearance, pose, material, light)"),
)

BOXES_SYSTEM = """You improve the box descriptions of a MOSS-Image layout. The user placed boxes on a picture; each box has a type (character = a person, object = a thing or an area, text = written words), a place on the picture and a short description. You rewrite each description SEPARATELY so the image model draws exactly that thing in that box.

RULES
- Each description describes ONLY what is inside its own box. Never move content from one box into another, never describe the whole scene inside a box, never mention other boxes, positions, coordinates or sizes.
- Every box has a FREEDOM: "locked" = return the description exactly as given; "low" = keep the user's words, only fix grammar and make vague words concrete, add nothing; "medium" = keep everything, add only a little plausible visible detail; "high" = keep everything and describe it richly. A box's freedom always wins over the general creativity.
- Keep the user's facts: who, what, how many, clothing, colours, style, pose, exclusions. Never add people, objects or text that the user did not write.
- Text boxes: never change, translate or repeat the words to write (they are kept by the program); describe only how the lettering looks (typeface, weight, colour, size, surface).
- The global description (summary) describes the whole picture: medium, style, setting, light, palette - not the contents of each box again.
- English prose (or the user's language when they ask), concrete visible words, no quality tags, no coordinates.

WHAT TO RETURN
Return ONLY one JSON object, nothing before or after it:
{"summary": "<the improved global description>", "boxes": [{"n": 1, "description": "<the improved description of box 1>"}, {"n": 2, "description": "..."}]}
One entry per box number given, in the same order. Escape double quotes inside strings as \\"."""


def freedom_of(strict):
    for level, label, rule in FREEDOM:
        if strict >= level:
            return label, rule
    return FREEDOM[-1][1], FREEDOM[-1][2]


def where(b):
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    col = "left" if cx < 0.34 else "right" if cx > 0.66 else "centre"
    row = "top" if cy < 0.34 else "bottom" if cy > 0.66 else "middle"
    return f"{row} {col}, about {round(b['w'] * 100)}% wide and {round(b['h'] * 100)}% tall"


def boxes_message(prompt, boxes, width, height, n_pics, main_freedom):
    rows = []
    for i, b in enumerate(boxes, 1):
        label, rule = freedom_of(b.get("strict", 0))
        row = {"n": i, "type": b["type"], "place": where(b), "description": b["desc"], "freedom": f"{label} ({rule})"}
        if b["type"] == "text":
            row["words (kept by the program)"] = b["text"]
        rows.append(row)
    msg = {"summary": prompt.strip(), "summary freedom": main_freedom, "picture": f"{width} x {height}", "boxes": rows}
    return ("Rewrite these layout descriptions:\n" + json.dumps(msg, ensure_ascii=False, indent=1) + picture_note(n_pics))


def merge_boxes(answer, prompt, boxes):
    """-> (new prompt, new boxes, per-box changes, notes). Geometry, types, words and pictures never change; a locked
    box is never changed whatever the answer says; a missing entry keeps the user's text."""
    data = find_json(answer)
    notes = []
    if data is None:
        return prompt, boxes, [], ["the answer could not be read: nothing changed"]
    new_prompt = data.get("summary") if isinstance(data.get("summary"), str) and data.get("summary").strip() else prompt
    if isinstance(data.get("summary"), dict):
        new_prompt = str(data["summary"].get("caption") or prompt)
    got = {}
    for e in data.get("boxes", []) if isinstance(data.get("boxes"), list) else []:
        if isinstance(e, dict):
            try:
                got[int(e.get("n"))] = str(e.get("description") or e.get("caption") or "").strip()
            except (TypeError, ValueError):
                continue
    out, changes = [], []
    for i, b in enumerate(boxes, 1):
        nb = dict(b)
        label, _ = freedom_of(b.get("strict", 0))
        if label == "locked":
            changes.append({"n": i, "before": b["desc"], "after": b["desc"], "locked": True})
        elif got.get(i):
            nb["desc"] = got[i]
            changes.append({"n": i, "before": b["desc"], "after": got[i]})
        else:
            notes.append(f"box {i}: no answer, kept yours")
            changes.append({"n": i, "before": b["desc"], "after": b["desc"]})
        out.append(nb)
    return new_prompt.strip(), out, changes, notes


def enhance_boxes(clip, prompt, boxes, creativity, variation, width, height, images=None, generate_fn=None):
    """-> (prompt, boxes, report, changes). Never raises: an unusable answer keeps everything as it was."""
    t0 = time.time()
    open_boxes = [b for b in boxes if freedom_of(b.get("strict", 0))[0] != "locked"]
    if not open_boxes and not prompt.strip():
        return prompt, boxes, "All boxes are locked (strict 1) and the prompt is empty - nothing to rewrite.", []
    c = float(creativity)
    main = "low (keep the user's words, make them concrete)" if c < 0.34 else \
        "medium (add a little plausible visible detail)" if c < 0.67 else "high (describe richly)"
    n_pics = len(images) if images else 0
    user = boxes_message(prompt, boxes, width, height, n_pics, main)
    temperature = 0.2 + 0.8 * c
    max_length = 220 + 160 * len(boxes)
    try:
        answer = (generate_fn or generate)(clip, BOXES_SYSTEM, user, images or None, temperature, int(variation), max_length)
    except Exception as error:
        return prompt, boxes, f"Enhancer failed ({type(error).__name__}: {error}) - nothing changed.", []
    new_prompt, new_boxes, changes, notes = merge_boxes(answer, prompt, boxes)
    changed = sum(1 for ch in changes if ch["after"] != ch["before"])
    report = (f"Enhancer ON: {len(boxes)} boxes rewritten one by one ({changed} changed, "
              f"{sum(1 for ch in changes if ch.get('locked'))} locked), {time.time() - t0:.1f}s, "
              f"temperature {temperature:.2f}, variation {variation}")
    if notes:
        report += "\nNotes: " + "; ".join(notes)
    return new_prompt, new_boxes, report, changes
