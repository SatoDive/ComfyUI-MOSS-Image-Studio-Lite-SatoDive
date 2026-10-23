"""Nodes: MOSS Generate Lite, MOSS Prompt Enhancer Lite (SatoDive) - no reference pictures."""

import json

import torch

from comfy_api.latest import io

from . import enhancer, studio

TAG = "[MOSS Studio Lite]"


class MOSSPromptEnhancerLite_SatoDive(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MOSSPromptEnhancerLite_SatoDive",
            display_name="MOSS Prompt Enhancer Lite (SatoDive)",
            category="SatoDive/MOSS-Image Lite",
            description="Write your idea in plain words (any language); switch ON and MOSS-Image's own text encoder "
                        "(Qwen3.5-9B, the same file as the CLIP) rewrites it following the official MOSS prompt guide "
                        "into a detailed caption or a Layout prompt. OFF = your text is used as it is (no LLM call).",
            inputs=[
                io.Clip.Input("clip", tooltip="The MOSS text encoder (CLIPLoader, type moss_image) - the same file "
                              "your render uses, so it loads only once."),
                io.String.Input("text", multiline=True, dynamic_prompts=True, default="",
                                tooltip="Your idea in plain words, any language. Put words that must appear in the "
                                        "image in quotes."),
                io.Boolean.Input("enhance", default=False, label_on="ON - rewrite with Qwen3.5",
                                 label_off="OFF - use my text as it is",
                                 tooltip="OFF: your text goes to the render unchanged and the LLM never runs. ON: the "
                                         "rewrite runs once and is reused until you change the text or a setting."),
                io.Combo.Input("output", options=enhancer.MODES, default=enhancer.MODES[0],
                               tooltip="auto: the official rule - a caption for ordinary images, a Layout (boxes) "
                                       "for posters / exact text placement. caption / layout: force one."),
                io.Combo.Input("detail", options=enhancer.DETAIL, default=enhancer.DETAIL[0],
                               tooltip="official = the MOSS guide's lengths (220-320 words, 320-500 for posters)."),
                io.Float.Input("creativity", default=0.25, min=0.0, max=1.0, step=0.05,
                               tooltip="0 = strict (only what you wrote, made concrete), 1 = free. Temperature "
                                       "0.2 + 0.8 x this."),
                io.Int.Input("variation", default=0, min=0, max=0xffffffff,
                             tooltip="Change it to get another rewrite of the same text (the rewrite is cached "
                                     "otherwise, so a normal re-run never waits for the LLM)."),
                io.Int.Input("width", default=1024, min=256, max=4096, step=16,
                             tooltip="Picture size: Layout boxes are placed on it. Also given as an output - wire "
                                     "it to the render so both always match."),
                io.Int.Input("height", default=1024, min=256, max=4096, step=16),
                io.String.Input("layout", multiline=True, default="", optional=True,
                                tooltip="Layout boxes JSON (from MOSS Generate Lite). With boxes, each box's description "
                                        "is rewritten on its own (its strict strength sets how freely) and the "
                                        "global text becomes the summary; places, types and words never change."),
            ],
            outputs=[
                io.String.Output(display_name="prompt", tooltip="Exactly what goes to the render (your text when "
                                 "OFF)."),
                io.Int.Output(display_name="width"),
                io.Int.Output(display_name="height"),
                io.String.Output(display_name="report"),
                io.String.Output(display_name="layout", tooltip="The boxes with their rewritten descriptions (your "
                                 "layout when OFF / no boxes)."),
            ],
        )

    @classmethod
    def execute(cls, clip, text, enhance, output, detail, creativity, variation, width, height, layout=""):
        if not enhance:          # off means off: no tokenizer, no LLM, the text untouched
            report = "Enhancer OFF: your text is used as it is."
            print(f"{TAG} {report}")
            return io.NodeOutput(text, width, height, report, layout or "")
        pics = None
        boxes = studio.parse_layout(layout or "")
        if boxes:
            prompt, new_boxes, report, _ = enhancer.enhance_boxes(clip, text, boxes, creativity, variation, width,
                                                                 height, pics)
            new_layout = json.dumps({"boxes": new_boxes}, ensure_ascii=False)
            print(f"{TAG} {report}")
            return io.NodeOutput(prompt, width, height, report, new_layout)
        prompt, report = enhancer.enhance(clip, text, output, detail, creativity, variation, width, height, pics)
        print(f"{TAG} {report}\n{TAG} final prompt:\n{prompt}")
        return io.NodeOutput(prompt, width, height, report, layout or "")


class MOSSGenerateLite_SatoDive(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        import comfy.samplers
        return io.Schema(
            node_id="MOSSGenerateLite_SatoDive",
            display_name="MOSS Generate Lite (SatoDive)",
            category="SatoDive/MOSS-Image Lite",
            description="The whole MOSS-Image job in one node, no reference pictures: text-to-image, Layout (draw "
                        "boxes on the node, a prompt and a strict strength per box), img2img / inpaint. Saves with the "
                        "workflow inside the PNG.",
            inputs=[
                io.Model.Input("model", tooltip="UNETLoader (moss_image_*) -> optional LoraLoaderModelOnly (speed "
                               "LoRA)."),
                io.Clip.Input("clip", tooltip="CLIPLoader, type moss_image."),
                io.Vae.Input("vae", tooltip="VAELoader, flux2 vae."),
                io.String.Input("prompt", multiline=True, dynamic_prompts=True, default="",
                                tooltip="What to make. With layout boxes it becomes the global description."),
                io.Int.Input("width", default=1024, min=256, max=4096, step=16),
                io.Int.Input("height", default=1024, min=256, max=4096, step=16),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=True),
                io.Int.Input("steps", default=8, min=1, max=200,
                             tooltip="8 with the 8-step DMD LoRA, 4 with the 4-step LoRA, 25-50 without a LoRA."),
                io.Float.Input("cfg", default=1.0, min=1.0, max=10.0, step=0.1, round=0.01,
                               tooltip="1 with a speed LoRA (fastest: the negative is not even encoded), 2.5-3 "
                                       "without."),
                io.Combo.Input("sampler_name", options=comfy.samplers.KSampler.SAMPLERS, default="euler"),
                io.Combo.Input("scheduler", options=comfy.samplers.KSampler.SCHEDULERS, default="simple"),
                io.Float.Input("denoise", default=1.0, min=0.0, max=1.0, step=0.01,
                               tooltip="With an image: 0.5 = small change, 0.85 = new content, 1 = repaint."),
                io.String.Input("negative", multiline=True, default=studio.NEGATIVE,
                                tooltip="Only used when CFG > 1."),
                io.Boolean.Input("slg", default=False, label_on="SLG ON (layer 22)", label_off="SLG OFF",
                                 tooltip="Official skip-layer guidance on the negative branch (layer 22, first half "
                                         "of the steps). Only works with CFG > 1."),
                io.Int.Input("mask_grow", default=8, min=0, max=128,
                             tooltip="Inpaint: grow the painted mask by this many pixels (soft edges)."),
                io.Boolean.Input("save", default=True, label_on="save to output", label_off="preview only"),
                io.String.Input("filename_prefix", default="MOSS/studio"),
                io.String.Input("layout", multiline=True, default="",
                                tooltip="Layout boxes as JSON (drawn on the node's canvas). Empty = no layout."),
                io.Image.Input("image", optional=True, tooltip="img2img / inpaint source (its size wins)."),
                io.Mask.Input("mask", optional=True, tooltip="Inpaint area (paint it in Load Image's mask editor)."),
            ],
            outputs=[
                io.Image.Output(display_name="image"),
                io.String.Output(display_name="final_prompt", tooltip="Exactly what the model read."),
                io.String.Output(display_name="report"),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, model, clip, vae, prompt, width, height, seed, steps, cfg, sampler_name, scheduler, denoise,
                negative, slg, mask_grow, save, filename_prefix, layout, image=None, mask=None):
        import nodes as comfy_nodes
        images, final, report = studio.generate(model, clip, vae, prompt, width, height, seed, steps, cfg,
                                                sampler_name, scheduler, denoise, negative, slg, mask_grow, layout,
                                                image, mask)
        print(f"{studio.TAG} {report}")
        saver = comfy_nodes.SaveImage() if save else comfy_nodes.PreviewImage()
        hidden = getattr(cls, "hidden", None)          # None when called outside the executor (tests)
        ui = saver.save_images(images, filename_prefix if save else "MOSS_preview",
                               getattr(hidden, "prompt", None), getattr(hidden, "extra_pnginfo", None))["ui"]
        ui["moss_report"] = [report]
        ui["moss_prompt"] = [final]
        return io.NodeOutput(images, final, report, ui=ui)


NODES = [MOSSGenerateLite_SatoDive, MOSSPromptEnhancerLite_SatoDive]
