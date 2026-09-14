"""Auto-starts the Trump Tower MRQ render once the editor finishes loading.
Runs in the FULL GUI editor (Slate valid) — the path that renders correctly on macOS.
Guarded by out/ueframes/DONE flag. Quits the editor when the render finishes."""
import unreal, os

PROJ = "/Users/d/.zcode/workspace/default/trump-tower-flight"
OUT = PROJ + "/out/ueframes"
DONE = OUT + "/DONE"
STATE = {"tick": 0, "handle": None, "started": False}


def _log(m):
    unreal.log_warning("AUTORUN: " + m)


STATE = {"tick": 0, "handle": None, "started": False, "quit_at": None}


def _on_render_finished(executor, success):
    _log("render finished success=" + str(success))
    try:
        os.makedirs(OUT, exist_ok=True)
        n = len([f for f in os.listdir(OUT) if f.endswith(".png")])
        with open(DONE, "w") as f:
            f.write("success=%s frames=%d" % (success, n))
        _log("frames on disk: %d" % n)
    except Exception as e:
        _log("flag write failed: " + str(e))
    # delayed quit: quitting instantly mid-worker-teardown trips the FScheduler
    # shutdown assert (and its crash reporter); give the engine time to unwind
    STATE["quit_at"] = STATE["tick"] + 300


def _build_and_start(subsystem):
    queue = subsystem.get_queue()
    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.map = unreal.SoftObjectPath("/Game/Maps/TowerDusk.TowerDusk")
    job.sequence = unreal.SoftObjectPath("/Game/Seq/TowerSeq.TowerSeq")
    job.author = "autorun"

    cfg = job.get_configuration()
    out_setting = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out_setting.output_resolution = unreal.IntPoint(1920, 1080)
    out_setting.output_directory.path = OUT
    out_setting.file_name_format = "frame.{frame_number}"
    out_setting.zero_pad_frame_numbers = 4
    out_setting.flush_disk_writes_per_shot = True

    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.override_anti_aliasing = True
    aa.spatial_sample_count = 1
    aa.temporal_sample_count = 1

    try:
        executor = unreal.MoviePipelinePIEExecutor(subsystem)
    except Exception:
        executor = unreal.MoviePipelinePIEExecutor()
    executor.on_executor_finished_delegate.add_callable_unique(_on_render_finished)
    subsystem.render_queue_with_executor_instance(executor)
    _log("RENDER STARTED via PIE executor")


def _on_tick(dt):
    STATE["tick"] += 1
    qa = STATE.get("quit_at")
    if qa and STATE["tick"] >= qa:
        _log("quitting editor after unwind delay")
        unreal.SystemLibrary.quit_editor()
        return
    if STATE["started"]:
        return
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        name = world.get_name() if world else ""
        actors = len(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return
    if STATE["tick"] % 60 == 0:
        _log("waiting: world=%s actors=%d tick=%d" % (name, actors, STATE["tick"]))
    if STATE["tick"] < 120 or actors < 500 or "towerdusk" not in name.lower():
        return
    STATE["started"] = True
    try:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
    except Exception:
        pass
    _log("map ready (%s, %d actors) — starting render" % (name, actors))
    try:
        subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
        _build_and_start(subsystem)
    except Exception as e:
        _log("START FAILED: " + str(e))
        _log("retrying on next ticks")
        STATE["started"] = False


if os.path.exists(DONE):
    _log("DONE flag present — autorun skipped")
else:
    STATE["handle"] = unreal.register_slate_post_tick_callback(_on_tick)
    _log("registered; OUT=" + OUT)
