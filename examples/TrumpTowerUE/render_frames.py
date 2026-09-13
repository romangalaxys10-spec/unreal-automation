"""UE 5.8 headless render: Movie Render Queue, PIE executor, 1080p24 PNG frames.
Run WITHOUT -nullrhi (real Metal RHI required for frames)."""
import unreal

OUT_DIR = "/Users/d/.zcode/workspace/default/trump-tower-flight/out/ueframes"

subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue = subsystem.get_queue()

job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
job.map = unreal.SoftObjectPath("/Game/Maps/TowerDusk.TowerDusk")
job.sequence = unreal.SoftObjectPath("/Game/Seq/TowerSeq.TowerSeq")
job.author = "UE Automation"

cfg = job.get_configuration()
out_setting = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
out_setting.output_resolution = unreal.IntPoint(1920, 1080)
out_setting.output_directory.path = OUT_DIR
out_setting.file_name_format = "frame.{frame_number}"
out_setting.zero_pad_frame_numbers = 4
out_setting.flush_disk_writes_per_shot = True

cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa.override_anti_aliasing = True
aa.spatial_sample_count = 1
aa.temporal_sample_count = 1

game = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
game.game_mode_override = None

log = unreal.log_warning
log("QUEUE JOB READY: map=/Game/Maps/TowerDusk seq=/Game/Seq/TowerSeq -> " + OUT_DIR)

def on_finished(executor, success):
    unreal.log_warning("RENDER FINISHED success=" + str(success))
    unreal.SystemLibrary.quit_editor()

executor = unreal.MoviePipelinePIEExecutor()
executor.on_executor_finished_delegate.add_callable_unique(on_finished)
subsystem.render_queue_with_executor_instance(executor)
log("RENDER STARTED")
