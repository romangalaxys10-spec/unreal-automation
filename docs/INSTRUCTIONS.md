# INSTRUCTIONS — end-to-end headless UE5 cinematic

From zero to a rendered flyover MP4 without touching the UE GUI.

## 0. One-time setup

```bash
# Metal shader compiler (missing in fresh Xcode 26 installs — UE dies silently without it)
xcodebuild -runFirstLaunch
xcodebuild -downloadComponent MetalToolchain
```

Copy the example project scripts into your project:

```
YourProject/
├── YourProject.uproject          # enable plugins: PythonScriptPlugin,
│                                 # SequencerScripting, MovieRenderPipeline,
│                                 # EditorScriptingUtilities
├── Config/DefaultEngine.ini      # see examples/TrumpTowerUE/Config/
├── Content/Python/
│   ├── init_unreal.py            # import TowerExecutor
│   └── TowerExecutor.py          # MRQ runtime executor
└── Content/                      # your maps/sequences get saved here
```

## 1. Author the level (headless, no GPU needed)

```bash
UnrealEditor-Cmd YourProject.uproject -run=pythonscript \
  -script=build_level.py -unattended -nopause -nosplash -nullrhi -stdout -nosound
```

`build_level.py` (example provided) creates: the level, procedural buildings with a
28-facet sawtooth tower, imported PBR textures as materials, emissive windows,
street lights, animated car lights, a DirectionalLight + SkyAtmosphere + fog, a
CameraActor, and a LevelSequence (24 fps) with keyframed drone beats and a bound
camera-cut track.

## 2. PREVIEW (cheap) — always before the full render

Render only a short segment (or low res) and verify numerically:

```bash
UnrealEditor-Cmd YourProject.uproject <map> -game \
  -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor \
  -ExecutorPythonClass=/Engine/PythonTypes.TowerExecutor \
  -LevelSequence=/Game/Seq/TowerSeq.TowerSeq \
  -OutputDir=/tmp/preview -RenderOffscreen -windowed -resx=640 -resy=360 \
  -stdout -nopause -unattended
```

Then check frames with PIL: mean luminance, warm/blue ratios, variance. If black →
see "Troubleshooting" before burning an hour on the full render.

## 3. Full render

Same command without the low-res flags, 1920x1080, into your output dir.
Expect roughly 1-3 s/frame on Apple Silicon at 1080p with simple materials.

## 4. Assemble

```bash
ffmpeg -framerate 24 -i out/frame.%04d.png -i vo.wav -map 0:v -map 1:a \
  -c:v libx264 -crf 18 -c:a aac -movflags +faststart out.mp4
```

Or call the MCP tool `ue_assemble_mp4` which does this (plus fades) for you.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Engine exits silently ~60 s after start, trace daemon gets SIGTERM | Missing Metal Toolchain | `xcodebuild -runFirstLaunch` + `xcodebuild -downloadComponent MetalToolchain` |
| MRQ renders pure-black PNGs | macOS 27 beta + Metal + `-game` MRQ bug (verified on a trivial lit cube) | Render from GUI editor MRQ window; or OS/engine update; check `examples/build_min_level.py` bisect on your machine |
| `Unable to load plugin 'PythonEditorScriptPlugin'` | Plugin renamed in 5.x | Use `PythonScriptPlugin` |
| `create_material` missing on MaterialEditingLibrary | API moved to AssetTools | `AssetTools.create_asset(name, path, unreal.Material, unreal.MaterialFactoryNew())` |
| `MaterialExpressionTextureSample2D` / `VectorParameter` not found | Renamed in 5.x | `TextureSample`, `Constant3Vector` |
| Camera-cut binding fails / black video | Binding GUID drift | Build the ID: `oid = unreal.MovieSceneObjectBindingID(); oid.set_editor_property("guid", binding.get_id())` |
| SIGKILL on UE → crash-reporter crash loop | Shutdown assert in task-graph teardown | Terminate UE with SIGTERM and wait; clear `~/Library/Application Support/Epic/<Proj>/Crashes` |
| Python `print()` missing from log | stdout buffering in commandlet | Use `unreal.log_warning()` |

## MCP integration

See README. The server is intentionally dependency-free (raw JSON-RPC over stdio) so it
works with any MCP host. Keep executor references in module globals if you extend the
Python executor — unreferenced executors get garbage-collected mid-render.
