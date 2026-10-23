"""MOSS Generate: the whole MOSS-Image job in one node next to the native loaders, every setting a visible widget.

MOSS Generate Lite = text-to-image, Layout (boxes drawn on the node, compiled to the official Layout prompt, a strict
strength per box) and img2img / inpaint when an image (and mask) is connected - no reference pictures. Built from
ComfyUI's own pieces: native loaders, the native KSampler path (common_ksampler: progress, live preview, noise mask), native
SLG and Differential Diffusion.
"""

import hashlib
import json
import time
import weakref

import torch

import comfy.samplers
import nodes

from . import enhancer

TAG = "[MOSS Studio Lite]"
NEGATIVE = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"   # the official template's negative
BOX_TYPES = ("object", "character", "text")
# a box's strict strength -> one sentence after its caption (your setting per box; 0 = nothing added)
STRICT_SENTENCES = ((0.9, "Exactly as described, with nothing added and nothing else inside this area."),
                    (0.5, "Only this, nothing else inside this area."))


# ------------------------------------------------------------------------------------------------ layout
def _num(v, lo, hi, cast=float):
    try:
        return max(lo, min(hi, cast(v or 0)))
    except (TypeError, ValueError):
        return lo


def parse_layout(text):
    """Layout widget JSON -> list of boxes {x, y, w, h (0..1 of the picture), type, text, desc, ref, strict}."""
    if not text or not text.strip():
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    boxes = data.get("boxes", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    out = []
    for b in boxes:
        if not isinstance(b, dict):
            continue
        try:
            x, y, w, h = (float(b.get(k, 0)) for k in ("x", "y", "w", "h"))
        except (TypeError, ValueError):
            continue
        x0, y0 = max(0.0, min(x, x + w)), max(0.0, min(y, y + h))
        x1, y1 = min(1.0, max(x, x + w)), min(1.0, max(y, y + h))
        kind = b.get("type") if b.get("type") in BOX_TYPES else "object"
        text_ = str(b.get("text") or "").strip()
        desc = str(b.get("desc") or "").strip()
        if x1 - x0 <= 0 or y1 - y0 <= 0 or not (desc or text_):
            continue
        if kind == "text" and not text_:
            kind = "object"
        out.append({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "type": kind, "text": text_, "desc": desc,
                    "ref": 0, "strict": _num(b.get("strict"), 0.0, 1.0)})
    return out


def box_caption(b):
    """A box's caption as MOSS reads it: its description, its reference picture, its strict sentence."""
    cap = b["desc"] or (f"Lettering reading \"{b['text']}\"" if b["text"] else "")
    for level, sentence in STRICT_SENTENCES:
        if b.get("strict", 0) >= level:
            cap = cap.rstrip()
            if cap and cap[-1] not in ".!?\"'":
                cap += "."
            cap = f"{cap} {sentence}".strip()
            break
    return cap


def layout_prompt(prompt, boxes, width, height):
    """Prompt + boxes -> the official one-line MOSS Layout prompt (no boxes = the prompt as it is)."""
    if not boxes:
        return prompt
    items = []
    for b in boxes:
        item = {"label": b["type"], "caption": box_caption(b)}
        if b["type"] == "text":
            item["text"] = b["text"]
        item["bbox"] = [b["x"] * width, b["y"] * height, (b["x"] + b["w"]) * width, (b["y"] + b["h"]) * height]
        items.append(item)
    draft = {"summary": {"caption": prompt.strip() or "An image."}, "items": items}
    return enhancer.compile_layout(draft, width, height)


# ------------------------------------------------------------------------------------------------ encode cache
_COND = {}          # key -> (weakref to the encoder's patcher, its patches uuid, cond); last few only


def _cached(clip, key, make):
    """Encode once per (exact encoder object + its LoRA patches + key): a reroll never moves the 9B encoder back
    onto the GPU. Anything that cannot be matched exactly is encoded again (never stale)."""
    patcher = clip.patcher
    uuid = getattr(patcher, "patches_uuid", None)
    hit = _COND.get(key)
    if hit is not None and hit[0]() is patcher and hit[1] == uuid and uuid is not None:
        return hit[2], True
    cond = make()
    _COND.pop(key, None)
    if len(_COND) >= 6:
        _COND.pop(next(iter(_COND)))
    _COND[key] = (weakref.ref(patcher), uuid, cond)
    return cond, False


def _pix_key(images):
    h = hashlib.sha1()
    for im in images:
        t = (im.clamp(0, 1) * 255).round().to(torch.uint8).cpu().contiguous()
        h.update(str(tuple(t.shape)).encode())
        h.update(t.numpy().tobytes())
    return h.hexdigest()


def encode(clip, text):
    return _cached(clip, (text, getattr(clip, "layer_idx", None)),
                   lambda: clip.encode_from_tokens_scheduled(clip.tokenize(text)))


def zero_cond(cond):
    return [[torch.zeros_like(c[0]), {k: (torch.zeros_like(v) if torch.is_tensor(v) else v) for k, v in c[1].items()}]
            for c in cond]


def grow(mask, px):
    if px <= 0:
        return mask
    m = mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])).float()
    return torch.nn.functional.max_pool2d(m, kernel_size=2 * px + 1, stride=1, padding=px).reshape(mask.shape)


# ------------------------------------------------------------------------------------------------ the job
def generate(model, clip, vae, prompt, width, height, seed, steps, cfg, sampler_name, scheduler, denoise, negative,
             slg, mask_grow, layout, image=None, mask=None):
    """-> (images [B,H,W,3], final prompt, report)."""
    t0 = time.time()
    notes = []
    width, height = int(width) // 16 * 16, int(height) // 16 * 16
    if image is not None:
        image = image[:, :, :, :3]
        height, width = image.shape[1] // 16 * 16, image.shape[2] // 16 * 16
        notes.append(f"size from the image: {width}x{height}")
    boxes = parse_layout(layout)
    final = layout_prompt(prompt, boxes, width, height)
    if boxes:
        notes.append(f"layout: {len(boxes)} boxes")

    pos, cached = encode(clip, final)
    if cfg == 1.0:
        neg = zero_cond(pos)          # at CFG 1 the negative is never used: no second encode
    else:
        neg, _ = encode(clip, negative)
    if slg and cfg > 1.0:
        from comfy_extras.nodes_slg import SkipLayerGuidanceDiTSimple
        model = SkipLayerGuidanceDiTSimple.execute(model, 0.0, 0.5, "", "22").result[0]
        notes.append("SLG layer 22 (0-50%)")
    elif slg:
        notes.append("SLG ignored (needs CFG > 1)")

    inpaint = image is not None and mask is not None and float(mask.max()) > 0
    if image is not None:
        latent = {"samples": vae.encode(image[:, :height, :width])}
        if inpaint:
            m = mask if mask.ndim == 3 else mask.unsqueeze(0)
            m = torch.nn.functional.interpolate(m.unsqueeze(1).float(), size=(image.shape[1], image.shape[2]),
                                                mode="bilinear").squeeze(1)
            m = grow(m, int(mask_grow)).clamp(0, 1)
            latent["noise_mask"] = m[:, :height, :width].reshape((-1, 1, height, width))
            from comfy_extras.nodes_differential_diffusion import DifferentialDiffusion
            model = DifferentialDiffusion.execute(model.clone(), 1.0).result[0]
            notes.append(f"inpaint, mask grown {int(mask_grow)} px, denoise {denoise:g}")
        else:
            notes.append(f"img2img, denoise {denoise:g}" + (" (mask is empty: whole picture)" if mask is not None else ""))
    else:
        latent = {"samples": torch.zeros([1, 128, height // 16, width // 16], device="cpu")}
        if denoise < 1.0:
            notes.append("denoise < 1 without an image: treated as 1")
            denoise = 1.0

    out = nodes.common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, pos, neg, latent, denoise=denoise)[0]
    images = vae.decode(out["samples"])
    if images.ndim == 5:
        images = images.reshape((-1,) + images.shape[-3:])
    if inpaint:
        orig = image[:, :images.shape[1], :images.shape[2]].to(images)
        mm = latent["noise_mask"].reshape((-1, height, width, 1))[:, :images.shape[1], :images.shape[2]].to(images)
        images = orig * (1 - mm) + images * mm       # untouched pixels stay exactly the original
    secs = time.time() - t0
    report = (f"{width}x{height}, {steps} steps, CFG {cfg:g}, {sampler_name} / {scheduler}, seed {seed}, "
              f"{secs:.1f}s" + ("" if not cached else ", prompt encode reused") + (" | " + "; ".join(notes) if notes else ""))
    return images, final, report
