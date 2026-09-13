# Unreal Automation — MCP server, skill, and headless UE5 pipeline

Drive Unreal Engine 5 **headlessly** on macOS: author levels with Python, render
cinematic frames through Movie Render Queue, verify frames numerically, and assemble
an MP4 with ffmpeg. Ships as an MCP server + a `/unreal` skill for coding agents.

Born from a real production run: a procedural Manhattan-dusk + Trump Tower drone
flyover built and rendered with zero GUI interaction (see `examples/`).

## Repository layout

```
ue-automation/
├── mcp/ue_mcp_server.py        # zero-dependency stdio MCP server (JSON-RPC 2.0)
├── skill/unreal-smart/SKILL.md # agent skill: smart-preview workflow + 5.8 API traps
├── examples/TrumpTowerUE/      # reference project scripts (build_level.py, TowerExecutor.py, ...)
├── docs/INSTRUCTIONS.md        # step-by-step: project setup -> author -> render -> assemble
└── README.md
```

## Quick start

### 1. Requirements
- UE 5.x installed (tested on 5.8.2, Apple Silicon macOS). Path via `UE_EDITOR_CMD` env
  (default `/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd`).
- Xcode with the **Metal Toolchain**: `xcodebuild -runFirstLaunch` then
  `xcodebuild -downloadComponent MetalToolchain` (UE cannot compile shaders without it;
  missing toolchain = engine exits silently ~60 s after start).
- Python 3 (server) and ffmpeg (MP4 assembly).

### 2. Register the MCP server
In your MCP client config:

```json
{
  "mcpServers": {
    "unreal-automation": {
      "command": "python3",
      "args": ["/absolute/path/to/ue-automation/mcp/ue_mcp_server.py"],
      "env": {
        "UE_EDITOR_CMD": "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd",
        "UE_PROJECT": "/absolute/path/to/YourProject.uproject",
        "UE_FFMPEG": "/absolute/path/to/ffmpeg"
      }
    }
  }
}
```

Tools exposed: `ue_info`, `ue_run_python`, `ue_render_frames`, `ue_assemble_mp4`,
`ue_check_frames`.

### 3. Install the skill
Copy `skill/unreal-smart/` into your agent's skills root (e.g. `~/.agents/skills/`).
The skill encodes the smart-preview loop: author (cheap, `-nullrhi` OK) → preview render
(small/few frames, numeric fingerprint) → full render (GPU) → assemble → QA.

### 4. Headless pipeline (what the tools run)

```
# authoring (no GPU needed)
UnrealEditor-Cmd <proj>.uproject -run=pythonscript -script=build_level.py \
  -unattended -nopause -nosplash -nullrhi -stdout -nosound

# render (REAL GPU — never -nullrhi, you get black frames)
UnrealEditor-Cmd <proj>.uproject <map> -game \
  -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor \
  -ExecutorPythonClass=/Engine/PythonTypes.TowerExecutor \
  -LevelSequence=/Game/Seq/TowerSeq.TowerSeq \
  -OutputDir=/abs/out -RenderOffscreen -stdout -nosound -nopause -unattended

# assemble
ffmpeg -framerate 24 -i out/frame.%04d.png -i vo.wav -map 0:v -map 1:a \
  -c:v libx264 -crf 18 -c:a aac out.mp4
```

You need a Content/Python executor module (see `examples/TrumpTowerUE/TowerExecutor.py`)
plus `Content/Python/init_unreal.py` importing it.

## Known macOS issues (as of UE 5.8.2 / macOS 27.0 beta)

- **Black frames from `-game` MRQ**: on macOS 27.0 beta + Metal, Movie Render Queue in
  `-game` mode can emit pure-black PNGs even for trivial lit scenes (verified with a
  single-cube minimal level). The Blender/other-engine path is unaffected. Workarounds:
  render from the GUI editor's MRQ window, or wait for an engine/OS fix. This repo's
  `examples/` include a minimal bisect scene (`build_min_level.py`) to check your own
  machine in ~2 minutes.
- **Metal Toolchain missing** = engine exits silently ~60 s after start (SIGTERM to the
  trace daemon, no error in stdout). Fix: `xcodebuild -runFirstLaunch` +
  `xcodebuild -downloadComponent MetalToolchain`.
- Graceful shutdown matters: SIGKILLing UE mid-run triggers a shutdown assert chain
  (`FScheduler::StopWorkers`) that crashes the crash reporter itself.

## License / credits
Texture examples come from Poly Haven (CC0). Pipeline scripts MIT.
