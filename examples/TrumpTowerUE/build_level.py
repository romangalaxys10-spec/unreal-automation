"""UE 5.8 headless level build: Manhattan dusk + sawtooth Trump Tower + drone sequence.
Run: UnrealEditor-Cmd TrumpTowerUE.uproject -run=pythonscript -script=build_level.py -unattended -nullrhi -stdout
Coordinates: 1 uu = 1 cm. Blender metres x100.
"""
import unreal, math, random, os

rng = random.Random(42)
ASSETS_SRC = "/Users/d/.zcode/workspace/default/trump-tower-flight/assets"
FLOOR = 348.0          # 3.48 m in uu
NOTCH = 120.0

def log(msg):
    unreal.log_warning("BUILD: " + msg)

def enum_member(cls, *names):
    """Defensive enum lookup: prefixed, unprefixed, or suffix match."""
    for n in names:
        if hasattr(cls, n):
            return getattr(cls, n)
    for n in dir(cls):
        if not n.startswith("_") and any(n.endswith(x) for x in names):
            return getattr(cls, n)
    return None

# ---------- level ----------
log("stage 0: level")
at_global = unreal.AssetToolsHelpers.get_asset_tools()

def asset_exists(p):
    for attr in ("does_asset_exists", "does_asset_exist"):
        fn = getattr(unreal.EditorAssetLibrary, attr, None)
        if fn:
            return fn(p)
    return False

if asset_exists("/Game/Maps/TowerDusk"):
    unreal.EditorAssetLibrary.delete_asset("/Game/Maps/TowerDusk")   # fresh level each run (no dup actors)
unreal.EditorLevelLibrary.new_level("/Game/Maps/TowerDusk")

def create_asset_safe(name, path, cls, factory=None):
    p = path + "/" + name
    if asset_exists(p):
        return unreal.load_asset(p)
    fac = factory() if isinstance(factory, type) else factory
    return at_global.create_asset(name, path, cls, fac)

# ---------- texture import ----------
log("stage 1: import textures")
at = unreal.AssetToolsHelpers.get_asset_tools()
tasks = []
HI = ("rectangular_paving", "large_sandstone_blocks_01")
SETS = ["asphalt_04", "rectangular_paving", "large_sandstone_blocks_01",
        "rectangular_facade_tiles", "concrete_tile_facade", "granite_tile", "metal_plate"]
for s in SETS:
    res = "2k" if s in HI else "1k"
    for k in ("diff", "nor_gl", "rough"):
        src = f"{ASSETS_SRC}/{s}/{s}_{k}_{res}.jpg"
        if not os.path.exists(src):
            log("MISSING TEXTURE: " + src)
            continue
        task = unreal.AssetImportTask()
        task.filename = src
        task.destination_path = "/Game/Tex"
        task.destination_name = f"T_{s}_{k}"
        task.automated = True
        task.save = True
        task.replace_existing = True
        tasks.append(task)
at.import_asset_tasks(tasks)
unreal.EditorAssetLibrary.save_directory("/Game/Tex")

def tex(name):
    return unreal.load_asset(f"/Game/Tex/T_{name}")

# ---------- materials ----------
log("stage 2: materials")
Melib = unreal.MaterialEditingLibrary

def pbr_material(name, asset, tiling, tint=None):
    m = create_asset_safe(name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    tc = Melib.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate)
    tc.u_tiling, tc.v_tiling = tiling, tiling
    d = Melib.create_material_expression(m, unreal.MaterialExpressionTextureSample)
    d.texture = tex(f"{asset}_diff")
    Melib.connect_material_expressions(tc, "Output", d, "UVs")
    color_out = ("d", "RGB")
    if tint:
        v = Melib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
        v.set_editor_property("constant", unreal.LinearColor(tint[0], tint[1], tint[2], 1))
        mul = Melib.create_material_expression(m, unreal.MaterialExpressionMultiply)
        Melib.connect_material_expressions(d, "RGB", mul, "A")
        Melib.connect_material_expressions(v, "RGB", mul, "B")
        color_out = ("mul", "RGB")
    src_node, src_out = (d, "RGB") if not tint else (mul, "RGB")
    Melib.connect_material_property(src_node, src_out, unreal.MaterialProperty.MP_BASE_COLOR)
    r = Melib.create_material_expression(m, unreal.MaterialExpressionTextureSample)
    r.texture = tex(f"{asset}_rough")
    Melib.connect_material_property(r, "RGB", unreal.MaterialProperty.MP_ROUGHNESS)
    n = Melib.create_material_expression(m, unreal.MaterialExpressionTextureSample)
    n.texture = tex(f"{asset}_nor_gl")
    try:
        n.sampler_type = unreal.SamplerSourceMode.SSM_TYPE_COLOR if not hasattr(unreal.SamplerSourceMode, "SSM_NORMALMAP") else n.sampler_type
    except Exception:
        pass
    Melib.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_NORMAL)
    Melib.recompile_material(m)
    return m

def flat(name, col, rough=0.5, metallic=0.0):
    m = create_asset_safe(name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    v = Melib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
    v.set_editor_property("constant", unreal.LinearColor(col[0], col[1], col[2], 1))
    Melib.connect_material_property(v, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    s = Melib.create_material_expression(m, unreal.MaterialExpressionScalarParameter)
    s.set_editor_property("default_value", rough)
    Melib.connect_material_property(s, "", unreal.MaterialProperty.MP_ROUGHNESS)
    s2 = Melib.create_material_expression(m, unreal.MaterialExpressionScalarParameter)
    s2.set_editor_property("default_value", metallic)
    Melib.connect_material_property(s2, "", unreal.MaterialProperty.MP_METALLIC)
    Melib.recompile_material(m)
    return m

def glow(name, col, strength):
    m = create_asset_safe(name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    domain = enum_member(unreal.MaterialDomain, "MD_UNLIT", "UNLIT")
    if domain:
        m.set_editor_property("material_domain", domain)
    v = Melib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
    v.set_editor_property("constant", unreal.LinearColor(col[0]*strength, col[1]*strength, col[2]*strength, 1))
    Melib.connect_material_property(v, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    Melib.recompile_material(m)
    return m

mat_asphalt  = pbr_material("M_Asphalt", "asphalt_04", 0.12)
mat_paving   = pbr_material("M_Paving", "rectangular_paving", 0.8)
mat_sand     = pbr_material("M_Sandstone", "large_sandstone_blocks_01", 0.3)
mat_fac_a    = pbr_material("M_FacadeA", "rectangular_facade_tiles", 0.15, tint=(0.30, 0.32, 0.38))
mat_fac_b    = pbr_material("M_FacadeB", "concrete_tile_facade", 0.18, tint=(0.32, 0.34, 0.38))
mat_roof     = pbr_material("M_RoofMetal", "metal_plate", 0.3)
mat_glass    = flat("M_BronzeGlass", (0.28, 0.16, 0.07), 0.12, 0.65)
mat_band     = flat("M_Band", (0.045, 0.04, 0.038), 0.5, 0.4)
mat_mullion  = flat("M_Mullion", (0.05, 0.045, 0.04), 0.45, 0.6)
mat_gold     = flat("M_Gold", (0.85, 0.60, 0.15), 0.22, 1.0)
mat_leaf     = flat("M_Leaf", (0.08, 0.16, 0.05), 0.8)
mat_ctx1     = flat("M_Ctx1", (0.05, 0.055, 0.07), 0.6)
mat_win      = glow("M_Window", (1.0, 0.72, 0.40), 2.6)
mat_lamp     = glow("M_Lamp", (1.0, 0.75, 0.45), 6.0)
mat_car_r    = glow("M_CarR", (1.0, 0.12, 0.06), 4.0)
mat_car_w    = glow("M_CarW", (1.0, 0.95, 0.85), 5.0)
mat_atrium   = glow("M_Atrium", (1.0, 0.78, 0.50), 1.6)
mat_water    = flat("M_Water", (0.55, 0.68, 0.85), 0.15)
mat_stone    = flat("M_StoneEdge", (0.42, 0.38, 0.32), 0.7)
mat_tifwin   = flat("M_TifWin", (0.25, 0.28, 0.30), 0.3, 0.4)

# ---------- spawn helper ----------
cube = unreal.load_asset("/Engine/BasicShapes/Cube")

def box(nm, w, d, h, x, y, z, mat):
    a = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x, y, z + h/2))
    a.set_actor_label(nm)
    smc = a.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_static_mesh(cube)
    a.set_actor_scale3d(unreal.Vector(w/100.0, d/100.0, h/100.0))
    smc.set_material(0, mat)
    return a

# ---------- ground + streets ----------
log("stage 3: streets")
box("ground", 70000, 70000, 10, 2000, 0, -12, mat_asphalt)
box("fifth_ave", 2200, 34000, 6, -3400, 0, 0, mat_asphalt)
box("sidewalk_w", 700, 34000, 22, -4850, 0, 0, mat_paving)
box("sidewalk_e", 500, 34000, 22, -2450, 0, 0, mat_paving)
for i, ys in enumerate((-16000, -9000, -2000, 5000, 12000)):
    box(f"cross_{i}", 26000, 1600, 6, 6000, ys, 0, mat_asphalt)

# ---------- Trump Tower: sawtooth tiers ----------
log("stage 4: tower")
TIERS = [(0, 6, 2000.0), (6, 20, 1800.0), (26, 3, 1650.0), (29, 27, 1800.0), (56, 2, 1600.0)]
for ti, (z0s, n_st, hw) in enumerate(TIERS):
    for si in range(n_st):
        z = (z0s + si) * FLOOR
        box(f"t{ti}_band_{si}", hw*2+50, hw*2+50, 62, 0, 0, z, mat_band)
        gz = z + 62
        gh = FLOOR - 66
        box(f"t{ti}_glass_{si}", hw*2-280, hw*2-280, gh, 0, 0, gz, mat_glass)
        bay_w = (hw*2 + 50) / 7
        for side in range(4):
            for b in range(7):
                if (b + si) % 2 == 0:
                    continue
                c = -hw - 25 + bay_w * (b + 0.5)
                off = hw - NOTCH/2
                if side == 0:   box(f"t{ti}_bay", bay_w*0.92, NOTCH, gh, c, -off, gz, mat_glass)
                elif side == 1: box(f"t{ti}_bay", bay_w*0.92, NOTCH, gh, c, off, gz, mat_glass)
                elif side == 2: box(f"t{ti}_bay", NOTCH, bay_w*0.92, gh, -off, c, gz, mat_glass)
                else:           box(f"t{ti}_bay", NOTCH, bay_w*0.92, gh, off, c, gz, mat_glass)

TOP_Z = 58 * FLOOR
box("roof_mech", 2200, 1800, 600, 0, 0, TOP_Z, mat_roof)
box("roof_mech2", 1000, 800, 400, -400, -300, TOP_Z + 600, mat_mullion)

box("atrium_glow", 40, 1400, 1200, -2040, 0, 0, mat_atrium)
box("entrance_canopy", 600, 1000, 50, -2300, 0, 750, mat_mullion)
box("sign_plate", 30, 1400, 260, -2030, 0, 1450, mat_gold)

log("stage 5: terrace")
for i in range(6):
    tx = -800 + i * 320
    box(f"tree_tr_{i}", 36, 36, 160, tx, 2150, 5*FLOOR, mat_mullion)
    box(f"tree_crown_{i}", 300, 300, 300, tx, 2150, 5*FLOOR + 180, mat_leaf)
box("terrace_edge", 2400, 40, 80, 0, 2100, 5*FLOOR, mat_stone)
box("fountain", 440, 440, 70, 600, 1950, 5*FLOOR, mat_water)

log("stage 6: tower windows")
for si in range(0, 58):
    z = si * FLOOR + 140
    for face in range(4):
        for k in range(5):
            if rng.random() < 0.55:
                continue
            off = (rng.random() - 0.5) * 2600
            t = 1940
            if face == 0:   box("tw", 110, 10, 150, off, -t, z, mat_win)
            elif face == 1: box("tw", 110, 10, 150, off, t, z, mat_win)
            elif face == 2: box("tw", 10, 110, 150, -t, off, z, mat_win)
            else:           box("tw", 10, 110, 150, t, off, z, mat_win)

# ---------- Manhattan context ----------
log("stage 7: context")
box("tiffany", 3400, 2200, 3120, -600, 4800, 0, mat_sand)
for wi in range(4):
    box("tif_win", 3000, 30, 160, -600, 3680, 400 + wi*720, mat_tifwin)

CTX = [
    (-9000, -6000, 2600, 2600, 12000, True), (-12000, 3000, 3000, 2600, 16000, False),
    (-9500, 11000, 2400, 2400, 14000, True), (-4000, -11000, 3000, 3000, 18000, False),
    (6000, -9000, 2600, 2600, 15000, True), (11000, -4000, 3000, 2800, 20000, False),
    (13000, 6000, 2600, 2600, 17000, True), (9000, 12000, 3000, 2600, 13000, False),
    (2000, 13000, 2600, 2400, 11000, True), (-6000, 16000, 2800, 2600, 15000, False),
    (16000, -11000, 3000, 2800, 12000, False), (-15000, -12000, 2800, 2800, 13000, False),
    (18000, 13000, 2800, 2600, 16000, False), (-17000, 6000, 2600, 2600, 14500, False),
]
for i, (cx, cy, cw, cd, h, fac) in enumerate(CTX):
    box(f"ctx_{i}", cw, cd, h, cx, cy, 0, (mat_fac_a if i % 2 == 0 else mat_fac_b) if fac else mat_ctx1)
    bands = int(h // 600)
    for b in range(bands):
        if rng.random() < 0.45:
            continue
        if abs(cx) > abs(cy):
            wx = cx - int(math.copysign(cw/2 + 10, cx))
            box(f"ctx{i}_w", 12, cw*0.7, 110, wx, cy, 300 + b*600, mat_win)
        else:
            wy = cy - int(math.copysign(cd/2 + 10, cy))
            box(f"ctx{i}_w", cw*0.7, 12, 110, cx, wy, 300 + b*600, mat_win)

for ly in range(-14000, 14001, 2800):
    box("lamp_pole", 24, 24, 550, -4000, ly, 20, mat_mullion)
    box("lamp_head", 70, 70, 70, -4000, ly, 590, mat_lamp)

# ---------- lights ----------
log("stage 8: lights")
sun = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500))
sun.set_actor_label("Sun")
sun.set_actor_rotation(unreal.Rotator(28.0, 100.0, 0.0), False)
sun_lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
sun_lc.set_intensity(3.0)
sun_lc.set_light_color(unreal.LinearColor(1.0, 0.55, 0.28, 1))

atmo = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
atmo.set_actor_label("Atmosphere")

fog = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
fog.set_actor_label("Fog")
fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fc.set_fog_density(0.004)
try:
    fc.set_fog_inscat_luminance(unreal.LinearColor(0.10, 0.15, 0.38, 1))
except Exception as e:
    log("fog luminance skip: " + str(e))

skylight = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300))
skylight.set_actor_label("SkyLight")
slc = skylight.get_component_by_class(unreal.SkyLightComponent)
slc.set_intensity(0.6)

ppv = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
ppv.set_actor_label("PP")
ppv.set_editor_property("unbound", True)
ppc = ppv.get_component_by_class(unreal.PostProcessComponent)
try:
    st = ppc.settings
    st.auto_exposure_min_brightness = 1.0
    st.auto_exposure_max_brightness = 2.0
    st.exposure_compensation = 1.0
    ppc.settings = st
except Exception as e:
    log("pp exposure skip: " + str(e))

# ---------- camera + sequence ----------
log("stage 9: sequence")
cam = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(0, 0, 200))
cam.set_actor_label("DroneCam")
ccam = cam.get_component_by_class(unreal.CameraComponent)
ccam.set_field_of_view(65.0)

at2 = unreal.AssetToolsHelpers.get_asset_tools()
seq = create_asset_safe("TowerSeq", "/Game/Seq", unreal.LevelSequence, unreal.LevelSequenceFactoryNew)
seq = unreal.load_asset("/Game/Seq/TowerSeq")
seq.set_display_rate(unreal.FrameRate(24, 1))
seq.set_playback_start(0)
seq.set_playback_end(1248)

binding = seq.add_possessable(cam)
trk = binding.add_track(unreal.MovieScene3DTransformTrack)
sec = trk.add_section()
sec.set_start_frame(0)
sec.set_end_frame(1248)

KEYS = [
    (0,    (-5200, 1400, 200),   (-1500, 0, 5500)),
    (140,  (-6000, -1000, 3500), (-1500, 0, 8500)),
    (280,  (-7000, -8500, 10000),(-500, 0, 12000)),
    (420,  (-1800, -10800, 12500),(0, 0, 11500)),
    (560,  (500, -4600, 9500),   (0, -1200, 10000)),
    (700,  (6200, -3000, 13500), (1200, 0, 13500)),
    (840,  (4200, 4400, 21800),  (-400, -400, 17800)),
    (980,  (11500, 12200, 16500),(0, 0, 10500)),
    (1120, (15000, 16000, 12500),(0, 0, 9200)),
    (1248, (16500, 17500, 11500),(0, 0, 9000)),
]
try:
    chans = sec.get_all_channels()
except AttributeError:
    data = sec.get_data()
    chans = data.channels
log("transform channels: " + str(len(chans)))
for f, cl, tl in KEYS:
    loc = unreal.Vector(cl[0], cl[1], cl[2])
    rot = unreal.MathLibrary.find_look_at_rotation(loc, unreal.Vector(tl[0], tl[1], tl[2]))
    vals = [loc.x, loc.y, loc.z, rot.roll, rot.pitch, rot.yaw]   # degrees for rotation channels
    for ci in range(6):
        chans[ci].add_key(unreal.FrameNumber(f), vals[ci])

cc = seq.add_track(unreal.MovieSceneCameraCutTrack)
ccs = cc.add_section()
ccs.set_start_frame(0)
ccs.set_end_frame(1248)
try:
    oid = unreal.MovieSceneObjectBindingID()
    oid.set_editor_property("guid", binding.get_id())
    ccs.set_camera_binding_id(oid)
    log("camera cut bound via guid")
except Exception as e:
    unreal.log_warning("BIND FALLBACK: " + str(e))

# ---------- save ----------
log("stage 10: save")
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.EditorLoadingAndSavingUtils.save_map(world, "/Game/Maps/TowerDusk")
unreal.EditorAssetLibrary.save_directory("/Game/Seq")
unreal.EditorAssetLibrary.save_directory("/Game/Tex")
unreal.EditorAssetLibrary.save_directory("/Game/Materials")
log("BUILD COMPLETE")
