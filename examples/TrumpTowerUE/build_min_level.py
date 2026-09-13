"""Minimal bisect scene: floor + lit cube + camera, 24 frames. If THIS renders lit,
the main level has a specific breaking element; if black, the -game MRQ path itself is broken."""
import unreal, math

log = lambda m: unreal.log_warning("MINI: " + m)

try:
    unreal.EditorLevelLibrary.new_level("/Game/Maps/MinTest")
except Exception as e:
    log("new_level: " + str(e))

cube = unreal.load_asset("/Engine/BasicShapes/Cube")

def box(nm, w, d, h, x, y, z, mat):
    a = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x, y, z + h/2))
    a.set_actor_label(nm)
    smc = a.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_static_mesh(cube)
    a.set_actor_scale3d(unreal.Vector(w/100.0, d/100.0, h/100.0))
    if mat:
        smc.set_material(0, mat)
    return a

Melib = unreal.MaterialEditingLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
m = at.create_asset("M_MinEmissive", "/Game/MinTest", unreal.Material, unreal.MaterialFactoryNew())
v = Melib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
v.set_editor_property("constant", unreal.LinearColor(1.0, 0.6, 0.2, 1))
Melib.connect_material_property(v, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
Melib.recompile_material(m)
m2 = at.create_asset("M_MinGray", "/Game/MinTest", unreal.Material, unreal.MaterialFactoryNew())
c = Melib.create_material_expression(m2, unreal.MaterialExpressionConstant3Vector)
c.set_editor_property("constant", unreal.LinearColor(0.4, 0.4, 0.4, 1))
Melib.connect_material_property(c, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
Melib.recompile_material(m2)

box("floor", 2000, 2000, 20, 0, 0, 0, m2)
box("cube", 100, 100, 100, 0, 0, 10, m)

# sun
sun = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 300))
sun.set_actor_rotation(unreal.Rotator(-45.0, 30.0, 0.0), False)
sun_lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
sun_lc.set_intensity(5.0)

# skylight so nothing is unlit
sky = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300))
sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.0)

# camera 3m in front of cube
cam = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(0, -300, 60))
cam.set_actor_rotation(unreal.Rotator(0.0, 90.0, 0.0), False)  # yaw 90 = face +Y toward cube

at2 = unreal.AssetToolsHelpers.get_asset_tools()
seq = at2.create_asset("MinSeq", "/Game/MinTest", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(24, 1))
seq.set_playback_start(0)
seq.set_playback_end(24)

binding = seq.add_possessable(cam)
trk = binding.add_track(unreal.MovieScene3DTransformTrack)
sec = trk.add_section()
sec.set_start_frame(0)
sec.set_end_frame(24)
chans = sec.get_all_channels()
for f, vals in [(0, [0, -300, 60, 0, 0, 90]), (24, [0, -280, 60, 0, 0, 90])]:
    fn = unreal.FrameNumber(f)
    for ci in range(6):
        chans[ci].add_key(fn, vals[ci])

cc = seq.add_track(unreal.MovieSceneCameraCutTrack)
ccs = cc.add_section()
ccs.set_start_frame(0)
ccs.set_end_frame(24)
try:
    oid = unreal.MovieSceneObjectBindingID()
    oid.set_editor_property("guid", binding.get_id())
    ccs.set_camera_binding_id(oid)
    log("camera bound")
except Exception as e:
    log("BIND FAIL " + str(e))

world = unreal.EditorLevelLibrary.get_editor_world()
unreal.EditorLoadingAndSavingUtils.save_map(world, "/Game/Maps/MinTest")
unreal.EditorAssetLibrary.save_directory("/Game/MinTest")
unreal.EditorAssetLibrary.save_directory("/Game/Seq")
log("MINI BUILD COMPLETE")
