# MOSS-Image Studio Lite - SatoDive (1.0.0)

Fast, simple **MOSS-Image** (OpenMOSS, 5B DiT + Qwen3.5-9B) in ComfyUI: one main node next to the native loaders,
every setting a visible widget, a drawable Layout canvas, inpaint, and a Prompt Enhancer that uses the model's own
text encoder.

## Video Tutorial & Walkthrough

<p align="center">
  <a href="https://www.youtube.com/watch?v=AWNb8O1pHVQ">
    <img src="https://img.youtube.com/vi/AWNb8O1pHVQ/maxresdefault.jpg" alt="MiniMax-H3 ComfyUI Tutorial" width="750">
  </a>
</p>

<p align="center">
  ▶️ <i>Click the image above to watch the complete step-by-step walkthrough on YouTube.</i>
</p>


📥 Download ComfyUI Workflow For Free:
<a href="https://www.patreon.com/SatoDive/posts/moss-image-might-173268998">Download the Workflow</a>


## Nodes
**MOSS Generate Lite (SatoDive)** - the whole job in one node
- Text-to-image with turbo defaults (8 steps, CFG 1 with the 8-step DMD LoRA).
- **Layout**: drag boxes on the node's canvas - move, resize, set each box's type (object / character / text), its
  own prompt and a **strict** strength (0 = free ... 1 = exactly your words, nothing else inside the box). Compiled
  to the official MOSS-Image Layout prompt.
- **Inpaint / img2img**: connect Load Image (paint the mask in the Mask Editor); only the painted area changes, the
  rest is pasted back pixel for pixel.
- Negative prompt and the official skip-layer guidance (layer 22) when CFG > 1.
- Saves to `output/MOSS` with the workflow inside the PNG; shows the last render's report and the exact final prompt.

**✨ Enhance** (button in the node) and **MOSS Prompt Enhancer Lite (SatoDive)**
- MOSS's own Qwen3.5-9B rewrites your plain words following the official MOSS-Image prompt guide: a detailed caption
  or a Layout (boxes) - with boxes, **each box is rewritten on its own** (strict 1 = never touched).
- Runs only when you click (a separate small job, nothing rendered); review Before / After, edit, then Apply.
- The node version is OFF by default (OFF = your text as it is, the LLM never runs).

The panel grows with its content and never shrinks a size you chose (right-click: *Fit the panel now*).

## Install
1. ComfyUI **v0.42 or newer** (native MOSS-Image support).
2. Copy this folder into `ComfyUI/custom_nodes` and restart ComfyUI. No extra Python packages.
3. Models (Comfy-Org/MOSS-Image on Hugging Face):
   - `diffusion_models`: `moss_image_sft_int8_convrot` (or bf16)
   - `text_encoders`: `qwen3.5_9b_int8_convrot` (CLIPLoader type `moss_image`)
   - `vae`: `flux2-vae`
   - optional turbo LoRA: `MOSS-Image-SFT-8-steps-dmd` (lodestones) with LoraLoaderModelOnly at 1.0
4. Graph: UNETLoader -> LoraLoaderModelOnly -> **MOSS Generate Lite**, plus CLIPLoader and VAELoader.

**Example workflows** are free on SatoDive's Patreon.

## Settings
| | steps | CFG | negative | SLG |
|---|---|---|---|---|
| Turbo (8-step DMD LoRA) | 8 | 1 | not used | off |
| Full quality (no LoRA) | 25-50 | 2.5-3 | official default | on |

## Changelog
- 1.0.0 - first release: MOSS Generate Lite (text-to-image, Layout canvas with strict boxes, inpaint), Enhance button +
  MOSS Prompt Enhancer Lite (caption / Layout / each box on its own), auto-grow panel.

## License
MIT - SatoDive
