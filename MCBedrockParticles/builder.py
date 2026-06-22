import bpy
import os
import json
from .parser import BedrockParticleParser
from .java_parser import JavaParticleParser
from .molang import evaluate
from .materials import create_particle_material, create_billboard_instance


JSON_CACHE = {}

def find_json_by_identifier(root_dir, target_identifier):
    if not JSON_CACHE:
        # Build cache once
        for root, _, files in os.walk(root_dir):
            for f in files:
                if f.endswith(".json"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8") as file:
                            import json
                            data = json.load(file)
                            if "particle_effect" in data:
                                ident = data["particle_effect"].get("description", {}).get("identifier", "")
                                if ident:
                                    JSON_CACHE[ident] = path
                    except Exception:
                        pass
    return JSON_CACHE.get(target_identifier)


def detect_format(filepath):
    """
    Auto-detect whether a JSON file is Bedrock or Java format.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception as e:
            print("Error parsing format:", e)
            return "unknown"

    if not isinstance(data, dict):
        return "unknown"

    if "particle_effect" in data or "minecraft:particle_effect" in data:
        return "bedrock"
    
    # Sometimes bedrock files are unwrapped
    if "components" in data and "description" in data:
        return "bedrock"

    # Java checks
    if "textures" in data or "values" in data:
        return "java"

    # Deep bedrock check
    for key, value in data.items():
        if isinstance(value, dict) and "description" in value and "components" in value:
            return "bedrock"

    return "unknown"


def resolve_texture_bedrock(context, parser, json_filepath):
    """
    Resolves a Bedrock particle texture to an absolute file path.
    Search order:
      1. Resource pack path set by user (exact path)
      2. Walk upward from the JSON file
      3. Relative to the JSON directory
      4. Deep recursive search for the filename in the resource pack and json dir
    """
    raw_tex = parser.get_texture_path()
    if not raw_tex:
        return ""

    if ":" in raw_tex:
        raw_tex = raw_tex.split(":", 1)[1]

    raw_tex = raw_tex.replace("\\", "/")
    extensions = [".png", ".tga", ".jpg", ".jpeg", ""]
    basename = os.path.basename(raw_tex)

    # Helper for deep search
    def deep_search(root_dir):
        for root, _, files in os.walk(root_dir):
            for f in files:
                name, ext = os.path.splitext(f)
                if name == basename and ext.lower() in extensions:
                    return os.path.join(root, f)
        return None

    # Search 1: User resource pack (from scene prop)
    rp_path = context.scene.mcbedrock_resource_pack_path
    if rp_path and os.path.isdir(bpy.path.abspath(rp_path)):
        rp_root = bpy.path.abspath(rp_path)
        for ext in extensions:
            candidate = os.path.normpath(os.path.join(rp_root, raw_tex + ext))
            if os.path.isfile(candidate):
                return candidate
                
    # Search 1.5: Permanent addon-installed vanilla_pack directory
    addon_rp_path = os.path.join(os.path.dirname(__file__), "vanilla_pack")
    if os.path.isdir(addon_rp_path):
        for ext in extensions:
            candidate = os.path.normpath(os.path.join(addon_rp_path, raw_tex + ext))
            if os.path.isfile(candidate):
                return candidate

    # Search 2: Walk upward from JSON
    json_dir = os.path.dirname(os.path.abspath(json_filepath))
    current = json_dir
    for _ in range(6):
        for ext in extensions:
            candidate = os.path.normpath(os.path.join(current, raw_tex + ext))
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Search 3: Relative to JSON
    for ext in extensions:
        candidate = os.path.normpath(os.path.join(json_dir, raw_tex + ext))
        if os.path.isfile(candidate):
            return candidate

    # Search 4: Deep recursive fallback (fixes Jedi DLC nested structures)
    if rp_path and os.path.isdir(bpy.path.abspath(rp_path)):
        found = deep_search(bpy.path.abspath(rp_path))
        if found:
            return found
            
    # Search 4.5: Deep recursive fallback on permanent vanilla_pack
    if os.path.isdir(addon_rp_path):
        found = deep_search(addon_rp_path)
        if found:
            return found

    # Search 5: Deep recursive fallback in JSON directory
    found = deep_search(json_dir)
    if found: return found

    # Search 5: Bundled fallback
    addon_dir = os.path.dirname(__file__)
    bundled_tex = os.path.join(addon_dir, "assets", f"{basename}.png")
    if os.path.isfile(bundled_tex):
        return bundled_tex

    return raw_tex


def resolve_texture_java(context, tex_relative, json_filepath):
    """
    Resolves a Java particle texture path to an absolute file path.
    Java textures live under: assets/<namespace>/textures/particle/<name>.png
    """
    extensions = [".png", ".tga", ".jpg", ".jpeg", ""]
    
    # Generate variations since tex_relative could be "particle/soul", "custom/soul", etc.
    variations = [
        tex_relative,
        f"textures/{tex_relative}",
        f"textures/particle/{tex_relative}",
        f"assets/minecraft/textures/{tex_relative}",
        f"assets/minecraft/textures/particle/{tex_relative}"
    ]

    # Search 1: User resource pack
    rp_path = context.scene.mcbedrock_resource_pack_path
    if rp_path and os.path.isdir(bpy.path.abspath(rp_path)):
        rp_root = bpy.path.abspath(rp_path)
        for var in variations:
            for ext in extensions:
                candidate = os.path.normpath(os.path.join(rp_root, var + ext))
                if os.path.isfile(candidate):
                    return candidate

    # Search 2: Walk upward from JSON
    json_dir = os.path.dirname(os.path.abspath(json_filepath))
    current = json_dir
    for _ in range(6):
        for var in variations:
            for ext in extensions:
                candidate = os.path.normpath(os.path.join(current, var + ext))
                if os.path.isfile(candidate):
                    return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Search 5: Bundled fallback
    addon_dir = os.path.dirname(__file__)
    basename = os.path.basename(tex_relative)
    bundled_tex = os.path.join(addon_dir, "assets", f"{basename}.png")
    if os.path.isfile(bundled_tex):
        return bundled_tex

    return tex_relative


def build_particle_system(context, filepath, texture_override="", spawn_offset=(0.0, 0.0, 0.0), force_loop=False, existing_emitter=None, interpolation='Closest'):
    """
    Main entrypoint. Detects format and routes to the correct builder.
    """
    fmt = detect_format(filepath)

    if fmt == "bedrock":
        return _build_bedrock(context, filepath, texture_override, spawn_offset, force_loop, existing_emitter, interpolation)
    elif fmt == "java":
        return _build_java(context, filepath, texture_override, spawn_offset, interpolation)
    else:
        raise ValueError(
            "Unrecognized particle JSON format. "
            "Expected Bedrock ('particle_effect') or Java ('textures') top-level key."
        )

def simulate_recursively(filepath, context, fps, duration_frames, start_frame=1, static_emitter_matrix=None, global_particles_dict=None, root_dir=None, depth=0):
    if global_particles_dict is None:
        global_particles_dict = {}
    if root_dir is None:
        root_dir = os.path.dirname(filepath)
    if depth > 10:
        print(f"Max sub-emitter depth reached. Aborting recursion for {filepath}")
        return global_particles_dict
        
    from .simulator import BedrockSimulator
    parser = BedrockParticleParser(filepath)
    ident = parser.get_identifier()
    
    sim = BedrockSimulator(
        parser, 
        fps=fps, 
        duration_frames=duration_frames, 
        start_frame=start_frame, 
        static_emitter_matrix=static_emitter_matrix
    )
    particles = sim.simulate()
    
    if ident not in global_particles_dict:
        global_particles_dict[ident] = {"parser": parser, "particles": []}
    global_particles_dict[ident]["particles"].extend(particles)
    
    if hasattr(sim, "all_triggered_events") and sim.all_triggered_events:
        for ev in sim.all_triggered_events:
            event_name = ev["event_name"]
            event_def = parser.events.get(event_name, {})
            pe = event_def.get("particle_effect", {})
            if pe and pe.get("type") == "emitter":
                effect_id = pe.get("effect")
                if effect_id:
                    sub_json_path = find_json_by_identifier(root_dir, effect_id)
                    if sub_json_path:
                        ev_start_frame = int(ev["time"] * fps) + 1
                        simulate_recursively(
                            sub_json_path, context, fps, duration_frames,
                            start_frame=ev_start_frame,
                            static_emitter_matrix=ev["matrix"],
                            global_particles_dict=global_particles_dict,
                            root_dir=root_dir,
                            depth=depth + 1
                        )
    return global_particles_dict


def _build_bedrock(context, filepath, texture_override="", spawn_offset=(0.0, 0.0, 0.0), force_loop=False, existing_emitter=None, interpolation='Closest'):
    """Build a baked particle system from a Bedrock particle JSON using the Python Simulator."""
    from .simulator import BedrockSimulator
    
    parser = BedrockParticleParser(filepath)
    ident = parser.get_identifier()
    short_name = ident.split(":")[-1] if ":" in ident else ident

    # Determine bake duration (default 250 if not set)
    bake_frames = getattr(context.scene, "mcbedrock_bake_frames", 250)
    fps = context.scene.render.fps

    emitter_matrices = None
    if existing_emitter:
        import mathutils
        emitter_matrices = []
        original_frame = context.scene.frame_current
        for f in range(bake_frames + 1):
            context.scene.frame_set(f)
            context.view_layer.update()
            mat = existing_emitter.matrix_world.copy()
            emitter_matrices.append(mat)
        context.scene.frame_set(original_frame)

    global_particles_dict = simulate_recursively(filepath, context, fps, bake_frames, static_emitter_matrix=None)

    if existing_emitter:
        emitter = existing_emitter
        group_col = emitter.users_collection[0] if emitter.users_collection else context.collection
        
        # Delete old particles
        mesh_children = [c for c in emitter.children if c.type == 'MESH']
        for c in mesh_children:
            bpy.data.objects.remove(c, do_unlink=True)
            
        # Clear out existing sim instance if any
        for c in group_col.objects:
            if c.name.startswith("Particle_") and c.parent is None:
                bpy.data.objects.remove(c, do_unlink=True)
    else:
        # Create Dedicated Collection
        col_name = f"MC_{short_name}"
        # Ensure unique name
        if col_name in bpy.data.collections:
            i = 1
            while f"{col_name}.{i:03d}" in bpy.data.collections:
                i += 1
            col_name = f"{col_name}.{i:03d}"
            
        group_col = bpy.data.collections.new(col_name)
        context.collection.children.link(group_col)

        # Create Parent Emitter Empty
        emitter = bpy.data.objects.new(f"Emitter_{short_name}", None)
        emitter.empty_display_type = 'SPHERE'
        emitter.empty_display_size = 0.5
        emitter.location = spawn_offset
        context.collection.objects.link(emitter)
        
        # Move emitter to new collection
        group_col.objects.link(emitter)
        for col in emitter.users_collection:
            if col != group_col:
                col.objects.unlink(emitter)

    warning = None

    for effect_id, effect_data in global_particles_dict.items():
        sub_parser = effect_data["parser"]
        particles = effect_data["particles"]
        if not particles:
            continue
        short_name = effect_id.split(":")[-1] if ":" in effect_id else effect_id
        parser = sub_parser
        # Billboard instance base

        # DO NOT pre-evaluate size at frame 0, as variables like variable.psize evaluate to 0.0 and break the mesh scale.
        # Instead, we create a normalized 1x1 plane and scale it per frame!
        facing_mode = parser.get_billboard_mode()
        base_instance = create_billboard_instance(context, ident, 1.0, 1.0, facing_mode=facing_mode)
        
        # Move base_instance to new collection
        group_col.objects.link(base_instance)
        for col in base_instance.users_collection:
            if col != group_col:
                col.objects.unlink(base_instance)

        # Texture
        if texture_override and os.path.isfile(texture_override):
            abs_tex = texture_override
        else:
            abs_tex = resolve_texture_bedrock(context, parser, filepath)

        if not os.path.isfile(abs_tex):
            warning = f"Texture not found: '{sub_parser.get_texture_path()}'. Set your Resource Pack path or use manual texture."

        create_particle_material(base_instance, abs_tex, parser.get_material_type(), is_lit=parser.has_lighting(), interpolation=interpolation)

        base_instance.hide_set(False)
        base_instance.hide_render = False
        
        # Enforce real-time playback in the viewport so heavy particles don't artificially slow down time
        context.scene.sync_mode = 'FRAME_DROP'
        
        # We will hide the base instance by scaling it to 0 or moving it out of view.
        # Actually, we can just let it exist but not render it directly, or hide it statically.
        base_instance.hide_viewport = True
        base_instance.hide_render = True

        kf_options = {'options': {'FAST'}} if bpy.app.version >= (2, 92, 0) else {}

        # Bake Particles
        for p in particles:
            if not p.history:
                continue
            p_obj = base_instance.copy()
            # Do NOT copy the mesh data; share it across all particles for performance!
            group_col.objects.link(p_obj)
            
            if not existing_emitter:
                p_obj.parent = emitter
                
            p_obj.name = f"Particle_{short_name}_{p.id}"
            
            # Keep them statically visible in the outliner so the depsgraph doesn't constantly rebuild
            p_obj.hide_viewport = False
            p_obj.hide_render = False
            
            frames = sorted(p.history.keys())
            first_frame = frames[0]
            last_frame = frames[-1]
            
            if not p_obj.animation_data:
                p_obj.animation_data_create()
            # Setup UVs on object so fcurves can bind
            p_obj["uv_offset_x"] = 0.0
            p_obj["uv_offset_y"] = 0.0
            p_obj["uv_scale_x"] = 1.0
            p_obj["uv_scale_y"] = 1.0
            p_obj["mc_alpha"] = 1.0

            action = bpy.data.actions.new(name=f"Anim_{p_obj.name}")
            p_obj.animation_data.action = action
            
            # Determine total frames: frame 0, frame first_frame-1 (if >1), all history frames, frame last_frame+1
            times = []
            _OFFSCREEN = (99999.0, 99999.0, 99999.0)
            
            locs_x, locs_y, locs_z = [], [], []
            scales_x, scales_y, scales_z = [], [], []
            colors_r, colors_g, colors_b, colors_a = [], [], [], []
            uv_ox, uv_oy, uv_sx, uv_sy = [], [], [], []
            rot_type = 'XYZ'
            rot_w, rot_x, rot_y, rot_z = [], [], [], []
            
            def add_frame(f, loc, sc, col, uvo, uvs, rtype, rval, hide):
                # We do NOT use hide arrays anymore, we rely entirely on scale (0,0,0) to hide particles.
                # Teleporting objects causes Eevee TAA ghosting and massive 3 FPS lag, so we rely on scale!
                times.append(f)
                locs_x.append(loc[0]); locs_y.append(loc[1]); locs_z.append(loc[2])
                scales_x.append(sc[0]); scales_y.append(sc[1]); scales_z.append(sc[2])
                colors_r.append(col[0]); colors_g.append(col[1]); colors_b.append(col[2]); colors_a.append(col[3])
                uv_ox.append(uvo[0]); uv_oy.append(uvo[1])
                uv_sx.append(uvs[0]); uv_sy.append(uvs[1])
                if rtype == 'QUATERNION':
                    rot_w.append(rval.w); rot_x.append(rval.x); rot_y.append(rval.y); rot_z.append(rval.z)
                else:
                    rot_w.append(0.0); rot_x.append(0.0); rot_y.append(0.0); rot_z.append(rval)
                    
            # Keyframe before birth (hidden via scale 0)
            import mathutils
            import math
            history_frames = p.history
            emitter_matrix = emitter_matrices[0] if emitter_matrices else emitter.matrix_world
            
            if first_frame > 1:
                first_state = history_frames[first_frame]
                first_loc = emitter_matrix @ mathutils.Vector((first_state['pos'].x, -first_state['pos'].z, first_state['pos'].y))
                add_frame(first_frame - 1, first_loc, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0), (1.0, 1.0), 'XYZ', 0.0, True)
                # Ensure frame 0 is also keyed so it stays hidden
                add_frame(0, first_loc, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0), (1.0, 1.0), 'XYZ', 0.0, True)

            # Insert history
            for frame in frames:
                state = history_frames[frame]
                loc = emitter_matrix @ mathutils.Vector((state['pos'].x, -state['pos'].z, state['pos'].y))
                sc = (state['scale_x'], state['scale_y'], 1.0)
                c = state.get('color', [1.0, 1.0, 1.0, 1.0])
                uvo = state.get('uv_offset', [0.0, 0.0])
                uvs = state.get('uv_scale', [1.0, 1.0])
                
                rot_z_deg = state.get('rot_z', 0.0)
                velocity = state.get('velocity', None)
                
                rt = 'XYZ'
                rv = math.radians(rot_z_deg)
                
                if facing_mode.startswith('direction_') or facing_mode == 'lookat_direction':
                    vel = state.get('custom_direction')
                    if vel is None or vel.length < 0.0001:
                        vel = velocity if velocity is not None and velocity.length > 0.0001 else state.get('spawn_direction')
                    if vel is not None and vel.length > 0.0001:
                        vel_norm = vel.normalized()
                        import mathutils
                        if facing_mode == 'lookat_direction':
                            cd = state.get('custom_direction')
                            if not cd: cd = mathutils.Vector((0, 0, -1))
                            bl_cd = mathutils.Vector((cd.x, -cd.z, cd.y)).normalized()
                            default_forward = mathutils.Vector((1, 0, 0))
                            rot_quat = default_forward.rotation_difference(bl_cd)
                            spin_quat = mathutils.Quaternion((0, 0, 1), math.radians(rot_z_deg))
                            final_quat = rot_quat @ spin_quat
                        else:
                            if facing_mode == 'direction_x':
                                default_forward = mathutils.Vector((1, 0, 0))
                            elif facing_mode == 'direction_z':
                                default_forward = mathutils.Vector((0, 0, 1))
                            else:
                                default_forward = mathutils.Vector((0, 1, 0))
                            forward = mathutils.Vector((vel_norm.x, -vel_norm.z, vel_norm.y))
                            rot_quat = default_forward.rotation_difference(forward)
                            spin_quat = mathutils.Quaternion((0, 0, 1), math.radians(rot_z_deg))
                            final_quat = rot_quat @ spin_quat
                        rt = 'QUATERNION'
                        rv = final_quat
                
                rot_type = rt # Remember last mode
                p_obj.rotation_mode = rt
                add_frame(frame, loc, sc, c, uvo, uvs, rt, rv, False)
                
            # Post-death state
            last_state = history_frames[last_frame]
            last_loc = emitter_matrix @ mathutils.Vector((last_state['pos'].x, -last_state['pos'].z, last_state['pos'].y))
            add_frame(last_frame + 1, last_loc, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0), (1.0, 1.0), 'XYZ', 0.0, True)
            
            # Build fcurves fast
            def apply_fcurve(data_path, idx, vals):
                if hasattr(action, 'fcurves'):
                    fc = action.fcurves.new(data_path=data_path, index=idx)
                else:
                    fc = action.fcurve_ensure_for_datablock(p_obj, data_path, index=idx)
                
                fc.keyframe_points.add(len(times))
                flat = [0.0] * (len(times) * 2)
                flat[0::2] = times
                flat[1::2] = vals
                fc.keyframe_points.foreach_set('co', flat)
                # Default linear, color/uv use constant
                if data_path.startswith('["uv_'):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
                else:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                        
            apply_fcurve("location", 0, locs_x)
            apply_fcurve("location", 1, locs_y)
            apply_fcurve("location", 2, locs_z)
            apply_fcurve("scale", 0, scales_x)
            apply_fcurve("scale", 1, scales_y)
            apply_fcurve("scale", 2, scales_z)
            apply_fcurve("color", 0, colors_r)
            apply_fcurve("color", 1, colors_g)
            apply_fcurve("color", 2, colors_b)
            apply_fcurve("color", 3, colors_a)
            apply_fcurve('["mc_alpha"]', 0, colors_a)
            apply_fcurve('["uv_offset_x"]', 0, uv_ox)
            apply_fcurve('["uv_offset_y"]', 0, uv_oy)
            apply_fcurve('["uv_scale_x"]', 0, uv_sx)
            apply_fcurve('["uv_scale_y"]', 0, uv_sy)
            if rot_type == 'QUATERNION':
                apply_fcurve("rotation_quaternion", 0, rot_w)
                apply_fcurve("rotation_quaternion", 1, rot_x)
                apply_fcurve("rotation_quaternion", 2, rot_y)
                apply_fcurve("rotation_quaternion", 3, rot_z)
            else:
                apply_fcurve("rotation_euler", 2, rot_z)
                
            # Interpolation is already applied during apply_fcurve
                                    
            # Push into NLA track so we can scale speed live
            track = p_obj.animation_data.nla_tracks.new()
            nla_strip = track.strips.new(action.name, int(action.frame_range[0]), action)
            p_obj.animation_data.action = None

        for obj in context.selected_objects:
            obj.select_set(False)
        emitter.select_set(True)
        context.view_layer.objects.active = emitter

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.overlay.show_relationship_lines = False

        if base_instance:
            bpy.data.objects.remove(base_instance, do_unlink=True)

    return {"warning": warning}

def _build_java(context, filepath, texture_override="", spawn_offset=(0.0, 0.0, 0.0), interpolation='Closest'):
    """Build a baked particle system from a Java particle JSON."""
    from .java_parser import JavaParticleParser
    
    parser = JavaParticleParser(filepath)
    ident = os.path.splitext(os.path.basename(filepath))[0]
    short_name = parser.name
    
    bake_frames = getattr(context.scene, "mcbedrock_bake_frames", 250)
    fps = context.scene.render.fps

    # Create Dedicated Collection
    col_name = f"MC_{short_name}"
    if col_name in bpy.data.collections:
        i = 1
        while f"{col_name}.{i:03d}" in bpy.data.collections:
            i += 1
        col_name = f"{col_name}.{i:03d}"
        
    group_col = bpy.data.collections.new(col_name)
    context.collection.children.link(group_col)

    # Java particles don't define emitter shape - use a point emitter
    import bmesh
    mesh = bpy.data.meshes.new(f"Emitter_{short_name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.02)
    bm.to_mesh(mesh)
    bm.free()
    
    emitter = bpy.data.objects.new(f"Emitter_{short_name}", mesh)
    emitter.location = spawn_offset
    context.collection.objects.link(emitter)
    emitter.display_type = 'WIRE'
    
    # Move emitter to new collection
    group_col.objects.link(emitter)
    for col in emitter.users_collection:
        if col != group_col:
            col.objects.unlink(emitter)

    mod = emitter.modifiers.new(name="JavaParticles", type='PARTICLE_SYSTEM')
    psys = emitter.particle_systems[mod.name]
    settings = psys.settings

    fps = context.scene.render.fps
    settings.count = 20
    settings.frame_start = 1
    settings.frame_end = int(5 * fps)
    settings.lifetime = int(1.0 * fps)
    settings.normal_factor = 1.0
    settings.emit_from = 'FACE'

    # Billboard instance
    instance_obj = create_billboard_instance(context, ident, 0.1, 0.1)
    
    # Move base_instance to new collection
    group_col.objects.link(instance_obj)
    for col in instance_obj.users_collection:
        if col != group_col:
            col.objects.unlink(instance_obj)

    # Texture resolution
    if texture_override and os.path.isfile(texture_override):
        abs_tex = texture_override
    else:
        first_tex = parser.get_first_texture_path()
        abs_tex = resolve_texture_java(context, first_tex, filepath) if first_tex else ""

    warning = None
    if not os.path.isfile(abs_tex):
        raw_paths = parser.get_texture_paths()
        warning = (
            f"Texture not found for Java particle '{short_name}'. "
            f"Looked for: {raw_paths[0] if raw_paths else '(none)'}. "
            f"Set your Resource Pack path or use manual texture."
        )

    create_particle_material(instance_obj, abs_tex, "particles_alpha", interpolation=interpolation)

    settings.render_type = 'OBJECT'
    settings.instance_object = instance_obj
    settings.particle_size = 1.0
    
    # Hide the source instance out of the way so it doesn't clutter the scene
    # We DO NOT use hide_set(True) because that breaks particle rendering in newer Blender versions!
    instance_obj.location = (0, 0, -100)
    instance_obj.hide_render = False

    for obj in context.selected_objects:
        obj.select_set(False)
    emitter.select_set(True)
    context.view_layer.objects.active = emitter

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.overlay.show_relationship_lines = False

    return {"warning": warning}
