"""MOSS-Image Studio Lite - SatoDive: no reference pictures.

- MOSS Generate Lite: text-to-image, Layout boxes drawn on the node (a prompt and a strict strength per box),
  img2img / inpaint - next to the native loaders, every setting a visible widget, turbo defaults.
- MOSS Prompt Enhancer Lite: the model's own Qwen3.5-9B rewrites plain words with the official MOSS prompt guide
  (caption, Layout, or each box on its own); the Generate panel runs it as a separate job with review before Apply.
Own node ids: installs next to the full MOSS-Image Studio pack without any clash.
"""

from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

WEB_DIRECTORY = "./web"

try:
    from .moss_ref.nodes import NODES
except Exception as error:  # show why instead of silently missing nodes
    import traceback
    traceback.print_exc()
    print(f"[MOSS-Image Studio Lite - SatoDive] failed to load: {error}")
    NODES = []

try:
    import comfy.ldm.moss_image  # noqa: F401
except Exception:
    print("[MOSS-Image Studio Lite - SatoDive] this ComfyUI has no MOSS-Image support (comfy/ldm/moss_image): update "
          "ComfyUI (v0.42 or newer).")


class MOSSStudioLiteExtension_SatoDive(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return NODES


async def comfy_entrypoint() -> MOSSStudioLiteExtension_SatoDive:
    return MOSSStudioLiteExtension_SatoDive()


__all__ = ["comfy_entrypoint", "WEB_DIRECTORY"]
