"""TowerFlipbookExecutor v3: -game flipbook via take_high_res_screenshot(camera=...).
No SceneCapture, no MRQ. Each tick: move the level CameraActor to the interpolated
drone transform and request a 1080p screenshot from that camera. Frames land in
<Project>/Saved/Screenshots; the assembler picks them up.

CLI:
  UnrealEditor-Cmd <proj> /Game/Maps/TowerDusk -game \
    -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor \
    -ExecutorPythonClass=/Engine/PythonTypes.TowerFlipbookExecutor \
    -OutputDir=/abs/out -stdout -nosound -nopause -unattended
"""
import unreal, math

FPS = 24
TOTAL = 1248
TAIL = 240  # extra ticks so queued screenshots flush before exit

KEYS = [
    (0,    (-5200, 1400, 200),    (-1500, 0, 5500)),
    (140,  (-6000, -1000, 3500),  (-1500, 0, 8500)),
    (280,  (-7000, -8500, 10000), (-500, 0, 12000)),
    (420,  (-1800, -10800, 12500),(0, 0, 11500)),
    (560,  (500, -4600, 9500),    (0, -1200, 10000)),
    (700,  (6200, -3000, 13500),  (1200, 0, 13500)),
    (840,  (4200, 4400, 21800),   (-400, -400, 17800)),
    (980,  (11500, 12200, 16500), (0, 0, 10500)),
    (1120, (15000, 16000, 12500), (0, 0, 9200)),
    (1248, (16500, 17500, 11500), (0, 0, 9000)),
]


@unreal.uclass()
class TowerFlipbookExecutor(unreal.MoviePipelinePythonHostExecutor):
    frameIndex = unreal.uproperty(int)
    cam = unreal.uproperty(unreal.CameraActor)

    def _post_init(self):
        self.frameIndex = 0
        self.cam = None

    @unreal.ufunction(override=True)
    def execute_delayed(self, inPipelineQueue):
        world = self.get_last_loaded_world()
        cam = unreal.GameplayStatics.get_actor_of_class(world, unreal.CameraActor)
        if cam is None:
            unreal.log_error("TOWERFLIP: no CameraActor in level")
            self.on_executor_finished_impl()
            return
        self.set_editor_property("cam", cam)
        unreal.log_warning("TOWERFLIP: camera bound, starting flipbook")

    @unreal.ufunction(override=True)
    def on_begin_frame(self):
        super(TowerFlipbookExecutor, self).on_begin_frame()
        f = self.get_editor_property("frameIndex") + 1
        if f > TOTAL + TAIL:
            unreal.log_warning("TOWERFLIP COMPLETE")
            self.on_executor_finished_impl()
            return
        cam = self.get_editor_property("cam")
        if cam is None:
            unreal.log_warning("TOWERFLIP: no camera — finishing")
            self.on_executor_finished_impl()
            return
        if f > TOTAL:
            return  # tail: let queued screenshots flush

        lo = hi = None
        for i in range(len(KEYS) - 1):
            if KEYS[i][0] <= f <= KEYS[i + 1][0]:
                lo, hi = KEYS[i], KEYS[i + 1]
                break
        if lo is None or hi is None:
            lo = hi = KEYS[-1]
        u = (f - lo[0]) / float(max(hi[0] - lo[0], 1))
        cam_loc = [lo[1][k] + (hi[1][k] - lo[1][k]) * u for k in range(3)]
        tgt = [lo[2][k] + (hi[2][k] - lo[2][k]) * u for k in range(3)]

        cam.set_actor_location(unreal.Vector(*cam_loc), False, False)
        rot = unreal.MathLibrary.find_look_at_rotation(
            unreal.Vector(*cam_loc), unreal.Vector(*tgt))
        cam.set_actor_rotation(rot, False)

        unreal.AutomationLibrary.take_high_res_screenshot(
            1920, 1080, "frame_%04d.png" % f, camera=cam)
        if f % 120 == 0 or f == TOTAL:
            unreal.log_warning("TOWERFLIP frame %d requested" % f)
        self.set_editor_property("frameIndex", f)
