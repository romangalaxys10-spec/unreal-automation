---
name: unreal-smart
description: Drive Unreal Engine 5 headlessly (build scenes, render cinematic frames via Movie Render Queue, assemble MP4) and preview a render before committing to the full one. Use for any "render in unreal / ue5 flyover / ue cinematic / unreal preview" request, or when the user types /unreal or /unreal smart.
---

# Unreal Engine 5 headless automation (smart-preview workflow)

Everything runs through `UnrealEditor-Cmd` — no GUI, no focus stealing. One working
reference project lives in `../examples/TrumpTowerUE/` (Manhattan dusk drone flyover).

## Preconditions (check once)

1. UE 5.x binary: `/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd` (adjust path per install).
2. Project plugins enabled in the `.uproject`: `PythonScriptPlugin` (prebuilt dylib),
   `SequencerScripting`, `MovieRenderPipeline`, `EditorScriptingUtilities`.
   NOTE: the plugin is `PythonScriptPlugin` — `PythonEditorScriptPlugin` no longer exists in 5.8.
3. ffmpeg for final assembly.

## The smart-preview loop (do this in order)

1. **Author** (cheap, `-nullrhi` OK) — build/modify the level with a Python script:
   `UnrealEditor-Cmd <proj>.uproject -run=pythonscript -script=build_level.py -unattended -nopause -nosplash -nullrhi -stdout`
2. **PREVIEW** (before the big render) — render a *short segment* at low sample counts to
   catch framing/lighting problems: pass a 24-72 frame range or reduce `-resx/-resy`,
   then fingerprint the preview frames (PIL: luminance, warm/blue ratios — you cannot trust eyeballs).
3. **Full render** (expensive, real GPU required):
   `UnrealEditor-Cmd <proj>.uproject <map> -game -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor -ExecutorPythonClass=/Engine/PythonTypes.<YourExecutor> -LevelSequence=<seq> -OutputDir=<dir> -windowed -resx=1920 -resy=1080 -log -stdout -nopause`
   CRITICAL: never add `-nullrhi` to a render pass — you get black frames.
4. **Assemble** frames + audio with ffmpeg → h264/aac MP4.
5. **QA numerically**: ffprobe container truth, frame count, PIL per-beat fingerprints.

## 5.8 API drift traps (verified the hard way)

- `unreal.MaterialEditingLibrary` lost `create_material` — create materials via
  `AssetTools.create_asset(name, path, unreal.Material, unreal.MaterialFactoryNew())`.
- `MaterialExpressionTextureSample2D` → `MaterialExpressionTextureSample`;
  `VectorParameter` → `Constant3Vector`.
- `set_static_mesh(mesh)` — no second arg. `set_actor_rotation(rot, False)` — teleport arg required.
- Slotted actions/sequencer: `section.get_all_channels()` (not `get_data()`),
  `channel.add_key(unreal.FrameNumber(f), value)` (not FrameTime).
- Camera-cut binding: `cut_section.set_camera_binding_id(oid)` where
  `oid = unreal.MovieSceneObjectBindingID(); oid.set_editor_property("guid", binding.get_id())`.
- Engine enum members drift (`MD_UNLIT` etc.) — use a `hasattr`-chain lookup helper.

## MCP server

`mcp/ue_mcp_server.py` is a zero-dependency stdio MCP server exposing the same steps as
tools (`ue_run_python`, `ue_render_frames`, `ue_assemble_mp4`, `ue_check_frames`, `ue_info`).
Point your MCP client at it (command: python3, args: [ue_mcp_server.py]) and it will show up
as the "unreal-automation" toolset. Env overrides: `UE_EDITOR_CMD`, `UE_PROJECT`, `UE_FFMPEG`.

## Example project

See `examples/` in the repo: `build_level.py` (procedural Manhattan + Trump Tower sawtooth),
`render_frames.py`, `TowerExecutor.py` (MRQ runtime executor), `init_unreal.py`.
