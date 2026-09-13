"""TowerExecutor: MRQ runtime executor for the Trump Tower drone flyover.
Runs in -game mode. CLI:
  UnrealEditor-Cmd <proj> /Game/Maps/TowerDusk -game \
    -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor \
    -ExecutorPythonClass=/Engine/PythonTypes.TowerExecutor \
    -LevelSequence=/Game/Seq/TowerSeq.TowerSeq -windowed -resx=1280 -resy=720 -log
"""
import unreal


@unreal.uclass()
class TowerExecutor(unreal.MoviePipelinePythonHostExecutor):
    activeMoviePipeline = unreal.uproperty(unreal.MoviePipeline)

    def _post_init(self):
        self.activeMoviePipeline = None

    @unreal.ufunction(override=True)
    def execute_delayed(self, inPipelineQueue):
        (cmdTokens, cmdSwitches, cmdParameters) = unreal.SystemLibrary.parse_command_line(
            unreal.SystemLibrary.get_command_line())
        level_sequence_path = None
        output_dir = None
        try:
            level_sequence_path = cmdParameters["LevelSequence"]
        except Exception:
            unreal.log_error("Missing -LevelSequence=/Game/Seq/TowerSeq.TowerSeq")
            self.on_executor_errored()
            return
        try:
            output_dir = cmdParameters["OutputDir"]
        except Exception:
            output_dir = "/Users/d/.zcode/workspace/default/trump-tower-flight/out/ueframes"

        unreal.log_warning("TOWEREXEC: seq=" + level_sequence_path + " out=" + output_dir)

        self.pipelineQueue = unreal.new_object(unreal.MoviePipelineQueue, outer=self)
        new_job = self.pipelineQueue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        new_job.sequence = unreal.SoftObjectPath(level_sequence_path)

        output_setting = new_job.get_configuration().find_or_add_setting_by_class(
            unreal.MoviePipelineOutputSetting)
        output_setting.output_resolution = unreal.IntPoint(1920, 1080)
        output_setting.output_directory.path = output_dir
        output_setting.file_name_format = "frame.{frame_number}"
        output_setting.zero_pad_frame_numbers = 4
        output_setting.flush_disk_writes_per_shot = True

        new_job.get_configuration().find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        new_job.get_configuration().find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)

        aa = new_job.get_configuration().find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.override_anti_aliasing = True
        aa.spatial_sample_count = 1
        aa.temporal_sample_count = 1

        new_job.get_configuration().initialize_transient_settings()

        self.activeMoviePipeline = unreal.new_object(
            unreal.MoviePipeline, outer=self.get_last_loaded_world(), base_type=unreal.MoviePipeline)
        self.activeMoviePipeline.on_movie_pipeline_work_finished_delegate.add_function_unique(
            self, "on_movie_pipeline_finished")
        self.activeMoviePipeline.initialize(new_job)

    @unreal.ufunction(override=True)
    def on_begin_frame(self):
        super(TowerExecutor, self).on_begin_frame()
        if self.activeMoviePipeline:
            pct = unreal.MoviePipelineLibrary.get_completion_percentage(self.activeMoviePipeline)
            unreal.log_warning("TOWEREXEC progress: " + str(pct))

    @unreal.ufunction(ret=None, params=[unreal.MoviePipelineOutputData])
    def on_movie_pipeline_finished(self, results):
        unreal.log_warning("TOWEREXEC FINISHED success=" + str(results.success))
        self.activeMoviePipeline = None
        self.on_executor_finished_impl()
