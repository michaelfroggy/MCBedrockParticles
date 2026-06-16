import random
import math
import mathutils

from .molang_parser import evaluate, execute_statements

class ParticleState:
    def __init__(self, id_val):
        self.id = id_val
        self.age = 0.0
        self.lifetime = 1.0
        self.position = mathutils.Vector((0.0, 0.0, 0.0))
        self.velocity = mathutils.Vector((0.0, 0.0, 0.0))
        self.spawn_direction = mathutils.Vector((0.0, 0.0, 1.0))
        self.size = [0.1, 0.1]
        self.color = [1.0, 1.0, 1.0, 1.0]
        self.uv_offset = [0.0, 0.0]
        self.uv_scale = [1.0, 1.0]
        self.random1 = random.random()
        self.random2 = random.random()
        self.random3 = random.random()
        self.random4 = random.random()
        self.active = True
        self.rotation = 0.0
        self.rotation_rate = 0.0
        self.custom_vars = {}

        # For exporting frames
        self.history = {} # frame_number -> {pos, scale_x, scale_y, rot_z}
        
        # Sub-emitter event tracking
        self.triggered_events = [] # list of {"time": float, "event_name": str, "matrix": mathutils.Matrix}
        self.fired_timeline_events = set()

class BedrockSimulator:
    def __init__(self, parser, fps=24, duration_frames=100, force_loop=False, emitter_matrices=None, start_frame=1, static_emitter_matrix=None):
        self.parser = parser
        self.fps = fps
        self.dt = 1.0 / fps
        self.duration_frames = duration_frames
        self.emitter_matrices = emitter_matrices
        self.start_frame = start_frame
        self.static_emitter_matrix = static_emitter_matrix
        
        self.particles = []
        self.all_triggered_events = []
        self.lifetime_events = self.parser.components.get("minecraft:particle_lifetime_events", {})
        
        self.emitter_age = 0.0
        self.anim_time = (start_frame - 1) * self.dt
        self.next_particle_id = 0
        self.emitter_custom_vars = {}
        self.particle_scale = 1.0
        self.animation_scale = 1.0
        
        init_comp = self.parser.components.get("minecraft:emitter_initialization", {})
        self.creation_expr = init_comp.get("creation_expression", "")
        self.per_update_expr = init_comp.get("per_update_expression", "")
        self.spawn_fraction = 0.0

        self.rate_mode, self.rate_amt, self.rate_max = self.parser.get_rate()
        self.emitter_lifetime = self.parser.get_emitter_lifetime()
        self.activation_expr = None
        if "minecraft:emitter_lifetime_expression" in self.parser.components:
            self.activation_expr = self.parser.components["minecraft:emitter_lifetime_expression"].get("activation_expression", 1.0)
        self.shape_type, self.shape_data = self.parser.get_shape()

        self.is_looping = force_loop or ('minecraft:emitter_lifetime_looping' in self.parser.components)
        if 'minecraft:emitter_lifetime_looping' in self.parser.components:
            loop_data = self.parser.components['minecraft:emitter_lifetime_looping']
            self.sleep_time_expr = loop_data.get('sleep_time', 0.0)
        else:
            self.sleep_time_expr = 0.0
            
        self.emitter_random_1 = random.random()
        self.emitter_random_2 = random.random()
        self.emitter_random_3 = random.random()
        self.emitter_random_4 = random.random()

    def get_context(self, particle=None):
        ctx = {
            'v': {
                'emitter_age': self.emitter_age,
                'emitter_lifetime': self.evaluate_val(self.emitter_lifetime, {'v': {}, 'q': {}, 't': {}}) if not callable(self.emitter_lifetime) else 1.0,
                'emitter_random_1': self.emitter_random_1,
                'emitter_random_2': self.emitter_random_2,
                'emitter_random_3': self.emitter_random_3,
                'emitter_random_4': self.emitter_random_4,
            },
            'q': {
                'anim_time': self.anim_time,
                'emitter_age': self.emitter_age,
                'emitter_lifetime': self.evaluate_val(self.emitter_lifetime, {'v': {}, 'q': {}, 't': {}}) if not callable(self.emitter_lifetime) else 1.0,
                'emitter_random_1': self.emitter_random_1,
                'emitter_random_2': self.emitter_random_2,
                'emitter_random_3': self.emitter_random_3,
                'emitter_random_4': self.emitter_random_4,
            },
            't': {}
        }

        # Comprehensive query.* stubs with sensible Bedrock defaults
        ctx['q'].update({
            'is_moving': 0.0,
            'is_on_ground': 1.0,
            'is_sneaking': 0.0,
            'is_swimming': 0.0,
            'is_gliding': 0.0,
            'distance_from_camera': 10.0,
            'target_x_rotation': 0.0,
            'target_y_rotation': 0.0,
            'modified_move_speed': 0.0,
            'ground_speed': 0.0,
            'vertical_speed': 0.0,
            'actor_count': 1.0,
            'time_of_day': 0.5,
            'moon_phase': 0.0,
            'health': 20.0,
            'max_health': 20.0,
            'life_time': self.emitter_age,
            # position stubs
            'position_x': 0.0,
            'position_y': 0.0,
            'position_z': 0.0,
        })

        ctx['v'].update(self.emitter_custom_vars)

        # Alias for MoLang parser
        ctx['variable'] = ctx['v']
        ctx['query'] = ctx['q']
        ctx['temp'] = ctx['t']

        if particle:
            ctx['v'].update({
                'particle_age': particle.age,
                'particle_random_1': particle.random1,
                'particle_random_2': particle.random2,
                'particle_random_3': particle.random3,
                'particle_random_4': particle.random4,
                'particle_lifetime': particle.lifetime,
            })
            # Mirror particle-specific values into query namespace
            ctx['q'].update({
                'particle_age': particle.age,
                'particle_lifetime': particle.lifetime,
                'particle_random_1': particle.random1,
                'particle_random_2': particle.random2,
                'particle_random_3': particle.random3,
                'particle_random_4': particle.random4,
            })
            if hasattr(particle, 'custom_vars'):
                ctx['v'].update(particle.custom_vars)
        return ctx

    def evaluate_val(self, val, ctx):
        if isinstance(val, dict) and "expression" in val:
            val = val["expression"]
            
        if isinstance(val, (int, float)):
            return float(val)
        elif isinstance(val, str):
            return evaluate(val.lower(), ctx)
        return 0.0

    def evaluate_curves(self, particle):
        curves = self.parser.particle_effect.get("curves", {})
        if not curves:
            return
            
        ctx = self.get_context(particle)
        for curve_name, curve_data in curves.items():
            input_val = self.evaluate_val(curve_data.get("input", 0.0), ctx)
            h_range = self.evaluate_val(curve_data.get("horizontal_range", 1.0), ctx)
            nodes = curve_data.get("nodes", [])
            
            if not nodes or h_range <= 0:
                particle.custom_vars[curve_name] = 0.0
                continue
                
            t = input_val / h_range
            
            if len(nodes) == 1:
                res = nodes[0]
            else:
                curve_type = curve_data.get("type", "linear")
                if curve_type == "catmull_rom" and len(nodes) >= 4:
                    n = len(nodes)
                    segment_count = n - 3
                    
                    t_clamped = max(0.0, min(1.0, t))
                    scaled_t = t_clamped * segment_count
                    
                    seg_idx = int(math.floor(scaled_t))
                    local_t = scaled_t - seg_idx
                    if seg_idx >= segment_count:
                        seg_idx = segment_count - 1
                        local_t = 1.0

                    p0 = nodes[seg_idx]
                    p1 = nodes[seg_idx + 1]
                    p2 = nodes[seg_idx + 2]
                    p3 = nodes[seg_idx + 3]

                    lt2 = local_t * local_t
                    lt3 = lt2 * local_t

                    res = 0.5 * (
                        (2 * p1) +
                        (-p0 + p2) * local_t +
                        (2 * p0 - 5 * p1 + 4 * p2 - p3) * lt2 +
                        (-p0 + 3 * p1 - 3 * p2 + p3) * lt3
                    )
                else:
                    segment_count = len(nodes) - 1
                    scaled_t = t * segment_count
                    index = int(math.floor(scaled_t))
                    local_t = scaled_t - index
                    
                    if index < 0:
                        res = nodes[0]
                    elif index >= segment_count:
                        res = nodes[-1]
                    else:
                        p1 = nodes[index]
                        p2 = nodes[min(segment_count, index + 1)]
                        res = p1 + (p2 - p1) * local_t
                        
            # Strip 'variable.' prefix if it exists to match our dict structure easily
            c_name = curve_name
            if c_name.startswith("variable."):
                c_name = c_name[9:]
            elif c_name.startswith("v."):
                c_name = c_name[2:]
            particle.custom_vars[c_name] = res

    def get_shape_offset_and_dir(self, ctx):
        # Default point
        offset = mathutils.Vector((0.0, 0.0, 0.0))
        direction = mathutils.Vector((0.0, 0.0, 1.0))
        
        # Base offset (can apply to any shape, but especially point)
        base_offset = self.shape_data.get("offset", [0.0, 0.0, 0.0])
        if isinstance(base_offset, list):
            ox = self.evaluate_val(base_offset[0] if len(base_offset)>0 else 0.0, ctx)
            oy = self.evaluate_val(base_offset[1] if len(base_offset)>1 else 0.0, ctx)
            oz = self.evaluate_val(base_offset[2] if len(base_offset)>2 else 0.0, ctx)
            offset = mathutils.Vector((ox, oy, oz))

        if self.shape_type == "sphere":
            radius = self.evaluate_val(self.shape_data.get("radius", 1.0), ctx)
            u = random.random()
            v = random.random()
            theta = 2 * math.pi * u
            phi = math.acos(2 * v - 1)
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            offset += mathutils.Vector((x, y, z))
            direction = mathutils.Vector((x, y, z)).normalized() if radius > 0 else direction
            
            if self.shape_data.get("surface_only", False) == False:
                # Inside sphere
                r = random.random() ** (1.0/3.0)
                offset = (offset - mathutils.Vector((ox, oy, oz))) * r + mathutils.Vector((ox, oy, oz))

        elif self.shape_type == "box":
            half_dims = self.shape_data.get("half_dimensions", [0.5, 0.5, 0.5])
            hx_dim = self.evaluate_val(half_dims[0] if len(half_dims)>0 else 0.5, ctx)
            hy_dim = self.evaluate_val(half_dims[1] if len(half_dims)>1 else 0.5, ctx)
            hz_dim = self.evaluate_val(half_dims[2] if len(half_dims)>2 else 0.5, ctx)
            x = random.uniform(-hx_dim, hx_dim)
            y = random.uniform(-hy_dim, hy_dim)
            z = random.uniform(-hz_dim, hz_dim)
            offset += mathutils.Vector((x, y, z))
            

            
        elif self.shape_type == "custom":
            # Offset is already evaluated above. Evaluate custom direction.
            custom_dir = self.shape_data.get("direction", [0.0, 0.0, 1.0])
            if isinstance(custom_dir, list):
                dx = self.evaluate_val(custom_dir[0] if len(custom_dir)>0 else 0.0, ctx)
                dy = self.evaluate_val(custom_dir[1] if len(custom_dir)>1 else 0.0, ctx)
                dz = self.evaluate_val(custom_dir[2] if len(custom_dir)>2 else 0.0, ctx)
                direction = mathutils.Vector((dx, dy, dz)).normalized()
            # direction can be an explicit velocity array expression in Bedrock
            dir_data = self.shape_data.get("direction", None)
            if isinstance(dir_data, list) and len(dir_data) == 3:
                dx = self.evaluate_val(dir_data[0], ctx)
                dy = self.evaluate_val(dir_data[1], ctx)
                dz = self.evaluate_val(dir_data[2], ctx)
                direction = mathutils.Vector((dx, dy, dz))
            else:
                direction = mathutils.Vector((0, 0, 1))

        elif self.shape_type == "disc":
            radius = self.evaluate_val(self.shape_data.get("radius", 1.0), ctx)
            offset_arr = self.shape_data.get("offset", [0, 0, 0])
            normal_arr = self.shape_data.get("plane_normal", [0, 1, 0])
            
            ox = self.evaluate_val(offset_arr[0] if len(offset_arr)>0 else 0, ctx)
            oy = self.evaluate_val(offset_arr[1] if len(offset_arr)>1 else 0, ctx)
            oz = self.evaluate_val(offset_arr[2] if len(offset_arr)>2 else 0, ctx)
            
            if isinstance(normal_arr, str):
                if normal_arr.lower() == "x": normal_arr = [1,0,0]
                elif normal_arr.lower() == "y": normal_arr = [0,1,0]
                elif normal_arr.lower() == "z": normal_arr = [0,0,1]
                else: normal_arr = [0,1,0]
                
            nx = self.evaluate_val(normal_arr[0] if len(normal_arr)>0 else 0, ctx)
            ny = self.evaluate_val(normal_arr[1] if len(normal_arr)>1 else 1, ctx)
            nz = self.evaluate_val(normal_arr[2] if len(normal_arr)>2 else 0, ctx)
            
            n = mathutils.Vector((nx, ny, nz))
            if n.length > 0: n.normalize()
            else: n = mathutils.Vector((0,1,0))
            
            if abs(n.z) < 0.99:
                u = mathutils.Vector((0,0,1)).cross(n).normalized()
            else:
                u = mathutils.Vector((1,0,0)).cross(n).normalized()
            v = n.cross(u).normalized()
            
            surface_only = self.shape_data.get("surface_only", False)
            angle = random.uniform(0, 2*math.pi)
            r = radius if surface_only else radius * math.sqrt(random.uniform(0, 1))
            
            point = u * (r * math.cos(angle)) + v * (r * math.sin(angle))
            offset = mathutils.Vector((ox, oy, oz)) + point
            
            direction = n

        direction_mode = self.shape_data.get("direction", "outwards")
        if direction_mode == "outwards":
            # Outwards is ALWAYS from the emitter origin (0,0,0) to the absolute particle spawn position
            direction = offset.normalized() if offset.length > 0 else direction
        elif direction_mode == "inwards":
            direction = -offset.normalized() if offset.length > 0 else direction
        elif isinstance(direction_mode, list) and len(direction_mode) == 3:
            dx = self.evaluate_val(direction_mode[0], ctx)
            dy = self.evaluate_val(direction_mode[1], ctx)
            dz = self.evaluate_val(direction_mode[2], ctx)
            custom_dir = mathutils.Vector((dx, dy, dz))
            if custom_dir.length > 0:
                direction = custom_dir.normalized()

        return offset, direction

    def spawn_particle(self, fraction_offset=0.0, frame=1):
        p = ParticleState(self.next_particle_id)
        self.next_particle_id += 1

        ctx = self.get_context(p)
        # B3: Apply sub-frame emitter_age offset BEFORE evaluating shape,
        # so offset expressions like 'radius*-math.sin(emitter_age*360)'
        # are evaluated at the correct sub-frame time for each spawned particle.
        if 'v' in ctx:
            ctx['v']['emitter_age'] = self.emitter_age + fraction_offset
        if 'variable' in ctx:
            ctx['variable']['emitter_age'] = self.emitter_age + fraction_offset

        # B2: Evaluate minecraft:particle_initialization creation expression at spawn
        p_init = self.parser.components.get("minecraft:particle_initialization", {})
        p_init_create = p_init.get("per_update_expression", "")  # runs at particle creation
        self.p_init_per_update = p_init.get("per_update_expression", "")
        if p_init_create:
            execute_statements(p_init_create, ctx)
            p.custom_vars.update(ctx.get('v', {}))

        # Evaluate lifetime
        life_expr = self.parser.get_particle_lifetime()
        p.lifetime = self.evaluate_val(life_expr, ctx)
        if p.lifetime <= 0:
            p.lifetime = 0.1

        # Evaluate shape pos and speed
        offset, direction = self.get_shape_offset_and_dir(ctx)
        
        # Add world-space emitter transform if available
        mat = None
        if self.static_emitter_matrix:
            mat = self.static_emitter_matrix
        elif self.emitter_matrices and frame < len(self.emitter_matrices):
            mat = self.emitter_matrices[frame]
            
        if mat is not None:
            
            # 1. Transform offset
            # Bedrock (x, y, z) -> Blender (x, z, -y)
            bl_offset = mathutils.Vector((offset.x, offset.z, -offset.y))
            # Apply matrix
            bl_offset = mat @ bl_offset
            # Blender (X, Y, Z) -> Bedrock (X, Z, -Y)
            offset = mathutils.Vector((bl_offset.x, bl_offset.z, -bl_offset.y))
            
            # 2. Transform direction (velocity vector)
            bl_dir = mathutils.Vector((direction.x, direction.z, -direction.y))
            # Apply matrix rotation only
            bl_dir = mat.to_3x3() @ bl_dir
            direction = mathutils.Vector((bl_dir.x, bl_dir.z, -bl_dir.y)).normalized()
            
            # Save matrix for linear_acceleration
            p.spawn_matrix = mat.to_3x3()
        else:
            p.spawn_matrix = None
            
        p.position = offset

        speed_expr = self.parser.get_initial_speed()
        speed = self.evaluate_val(speed_expr, ctx)
        p.spawn_direction = direction.copy() if hasattr(direction, 'copy') else direction
        
        # If direction is already a velocity vector (box emitter with direction array),
        # use it directly when speed is 1 (i.e. not explicitly set to a scalar)
        if speed == 0.0:
            p.velocity = mathutils.Vector((0.0, 0.0, 0.0))
        else:
            p.velocity = direction.normalized() * speed if direction.length > 0 else mathutils.Vector((0, 0, speed))
            # For box emitters with a full velocity direction, preserve the magnitude
            if self.shape_type == "box" and isinstance(self.shape_data.get("direction"), list):
                p.velocity = direction  # already the full velocity vector, ignore speed scalar

        spin_comp = self.parser.components.get("minecraft:particle_initial_spin", {})
        p.rotation = self.evaluate_val(spin_comp.get("rotation", 0.0), ctx)
        p.rotation_rate = self.evaluate_val(spin_comp.get("rotation_rate", 0.0), ctx)

        self.particles.append(p)
        
        # Check creation_event
        if self.lifetime_events:
            creation_event = self.lifetime_events.get("creation_event")
            if creation_event:
                p.triggered_events.append({
                    "time": self.anim_time,
                    "event_name": creation_event,
                    "matrix": mathutils.Matrix.Translation(mathutils.Vector((p.position.x, p.position.z, -p.position.y)))
                })
                self.all_triggered_events.append(p.triggered_events[-1])

    def simulate(self):
        ctx_init = self.get_context()
        execute_statements(self.creation_expr, ctx_init)
        self.emitter_custom_vars.update(ctx_init.get('v', {}))
        
        for frame in range(self.start_frame, self.duration_frames + 1):
            ctx_emitter = self.get_context()
            execute_statements(self.per_update_expr, ctx_emitter)
            self.emitter_custom_vars.update(ctx_emitter.get('v', {}))

            # Spawn logic
            ctx_emitter = self.get_context()
            emitter_life = self.evaluate_val(self.emitter_lifetime, ctx_emitter)
            max_particles = int(self.evaluate_val(self.rate_max, ctx_emitter))

            is_active = True
            if self.activation_expr is not None:
                is_active = self.evaluate_val(self.activation_expr, ctx_emitter) > 0.0
                
            if self.emitter_age <= emitter_life and is_active:
                if self.rate_mode == "instant" and not getattr(self, "has_spawned_instant", False):
                    amt = int(self.evaluate_val(self.rate_amt, ctx_emitter))
                    active_count = sum(1 for p in self.particles if p.active)
                    for _ in range(min(amt, max_particles - active_count)):
                        self.spawn_particle(frame=frame)
                    self.has_spawned_instant = True
                elif self.rate_mode == "steady":
                    rate = self.evaluate_val(self.rate_amt, ctx_emitter)
                    spawn_amount = rate * self.dt
                    self.spawn_fraction += spawn_amount
                    
                    spawn_count = int(self.spawn_fraction)
                    self.spawn_fraction -= spawn_count
                    
                    for i in range(spawn_count):
                        active_count = sum(1 for p in self.particles if p.active)
                        if active_count < max_particles:
                            fraction_offset = (i / max(1, spawn_count)) * self.dt
                            self.spawn_particle(fraction_offset, frame=frame)
            else:
                if self.is_looping:
                    sleep_time = self.evaluate_val(self.sleep_time_expr, ctx_emitter)
                    if self.emitter_age > emitter_life + sleep_time:
                        self.emitter_age = 0.0
                        self.has_spawned_instant = False

            # Update particles
            motion_dynamic = self.parser.components.get("minecraft:particle_motion_dynamic", {})
            motion_param = self.parser.components.get("minecraft:particle_motion_parametric", {})
            
            linear_accel = motion_dynamic.get("linear_acceleration", [0,0,0])
            linear_drag = motion_dynamic.get("linear_drag_coefficient", 0.0)

            size_data = self.parser.get_appearance_size()

            for p in self.particles:
                if not p.active:
                    continue

                # Pre-calculate curves for this frame and push them to context
                self.evaluate_curves(p)

                ctx_p = self.get_context(p)

                # Update physics
                if motion_param:
                    # Parametric overrides position directly based on expression
                    pos_expr = motion_param.get("relative_position", [0,0,0])
                    px = self.evaluate_val(pos_expr[0] if len(pos_expr)>0 else 0, ctx_p)
                    py = self.evaluate_val(pos_expr[1] if len(pos_expr)>1 else 0, ctx_p)
                    pz = self.evaluate_val(pos_expr[2] if len(pos_expr)>2 else 0, ctx_p)
                    p.position = mathutils.Vector((px, py, pz))
                else:
                    # Dynamic
                    ax = self.evaluate_val(linear_accel[0] if len(linear_accel)>0 else 0, ctx_p)
                    ay = self.evaluate_val(linear_accel[1] if len(linear_accel)>1 else 0, ctx_p)
                    az = self.evaluate_val(linear_accel[2] if len(linear_accel)>2 else 0, ctx_p)
                    
                    if getattr(p, 'spawn_matrix', None):
                        bl_accel = mathutils.Vector((ax, az, -ay))
                        bl_accel = p.spawn_matrix @ bl_accel
                        ax, ay, az = bl_accel.x, -bl_accel.z, bl_accel.y
                    
                    drag = self.evaluate_val(linear_drag, ctx_p)
                    
                    p.velocity.x += ax * self.dt
                    p.velocity.y += ay * self.dt
                    p.velocity.z += az * self.dt

                    p.velocity *= (1.0 - drag * self.dt)
                    
                    p.position += p.velocity * self.dt

                # --- Collision ---
                collision = self.parser.components.get("minecraft:particle_motion_collision")
                if collision:
                    # Check if collision is dynamically enabled/disabled
                    enabled_expr = collision.get("enabled", True)
                    if not self.evaluate_val(enabled_expr, ctx_p):
                        continue
                        
                    # Generic floor collision at Z=0 (Y=0 in Bedrock space)
                    # Note: Blender space has Z up. Bedrock pos has Y up. 
                    # p.position.y represents Bedrock altitude.
                    radius = self.evaluate_val(collision.get("collision_radius", 0.1), ctx_p)
                    if p.position.y <= radius:
                        if collision.get("expire_on_contact", False):
                            p.active = False
                        else:
                            # Bounce
                            restitution = self.evaluate_val(collision.get("coefficient_of_restitution", 0.5), ctx_p)
                            p.position.y = radius
                            if p.velocity.y < 0:
                                p.velocity.y = -p.velocity.y * restitution
                            
                            # Friction / Drag on contact
                            col_drag = self.evaluate_val(collision.get("collision_drag", 0.0), ctx_p)
                            p.velocity.x *= (1.0 - col_drag)
                            p.velocity.z *= (1.0 - col_drag)

                # --- Kill Plane ---
                kill_plane = self.parser.components.get("minecraft:particle_kill_plane")
                if kill_plane and isinstance(kill_plane, list) and len(kill_plane) >= 4:
                    a = self.evaluate_val(kill_plane[0], ctx_p)
                    b = self.evaluate_val(kill_plane[1], ctx_p)
                    c = self.evaluate_val(kill_plane[2], ctx_p)
                    d = self.evaluate_val(kill_plane[3], ctx_p)
                    val = a * p.position.x + b * p.position.y + c * p.position.z + d
                    # The kill plane equation is ax+by+cz+d=0. Usually particles are killed if they cross it.
                    # In Bedrock, it kills particles if the distance value > 0 (or < 0 depending on normal).
                    # We will kill if ax+by+cz+d > 0.
                    if val > 0:
                        p.active = False

                # Update size
                if isinstance(size_data, list):
                    w = self.evaluate_val(size_data[0] if len(size_data)>0 else 0.1, ctx_p)
                    h = self.evaluate_val(size_data[1] if len(size_data)>1 else 0.1, ctx_p)
                else:
                    w = self.evaluate_val(size_data, ctx_p)
                    h = w
                
                p.size = [max(0.001, w), max(0.001, h)]

                # Update color tinting
                tinting = self.parser.components.get("minecraft:particle_appearance_tinting", {})
                color_data = tinting.get("color", [1.0, 1.0, 1.0, 1.0])

                def srgb2lin(c):
                    c = max(0.0, min(1.0, c))
                    return (c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

                def parse_hex_color(hx):
                    """Parse a Bedrock hex color string. Bedrock uses #AARRGGBB format."""
                    if isinstance(hx, list):
                        ev = [self.evaluate_val(v, ctx_p) for v in hx]
                        rv, gv, bv = ev[0], ev[1], ev[2]
                        av = ev[3] if len(ev) > 3 else 1.0
                        return (srgb2lin(rv), srgb2lin(gv), srgb2lin(bv), av)
                    if isinstance(hx, str):
                        h = hx.lstrip('#')
                        if len(h) == 8:
                            # Bedrock: #AARRGGBB
                            av = int(h[0:2], 16) / 255.0
                            rv = int(h[2:4], 16) / 255.0
                            gv = int(h[4:6], 16) / 255.0
                            bv = int(h[6:8], 16) / 255.0
                        elif len(h) == 6:
                            # Standard: #RRGGBB
                            rv = int(h[0:2], 16) / 255.0
                            gv = int(h[2:4], 16) / 255.0
                            bv = int(h[4:6], 16) / 255.0
                            av = 1.0
                        else:
                            return (1.0, 1.0, 1.0, 1.0)
                        return (srgb2lin(rv), srgb2lin(gv), srgb2lin(bv), av)
                    return (1.0, 1.0, 1.0, 1.0)

                r, g, b, a = 1.0, 1.0, 1.0, 1.0

                if isinstance(color_data, dict):
                    # Gradient color
                    interpolant = self.evaluate_val(color_data.get("interpolant", 0.0), ctx_p)
                    # Wrap instead of hard-clamp: Catmull-Rom curves can output > 1.0 by design
                    # (e.g. rainbow nodes [1, 0, 1, 1.18]). Wrapping lets values like 1.05
                    # cycle back to 0.05 so the full gradient spectrum is used.
                    if interpolant < 0.0:
                        interpolant = 1.0 - ((-interpolant) % 1.0)
                    elif interpolant > 1.0:
                        interpolant = interpolant % 1.0
                    interpolant = max(0.0, min(1.0, interpolant))  # safety clamp after wrap
                    gradient = color_data.get("gradient", {})
                    if gradient:
                        if isinstance(gradient, list):
                            # Array format — equally spaced
                            n = len(gradient)
                            if n == 1:
                                r, g, b, a = parse_hex_color(gradient[0])
                            else:
                                scaled = interpolant * (n - 1)
                                gi = int(math.floor(scaled))
                                gi = max(0, min(n - 2, gi))
                                lt = scaled - gi
                                c1 = parse_hex_color(gradient[gi])
                                c2 = parse_hex_color(gradient[gi + 1])
                                r = c1[0] + (c2[0] - c1[0]) * lt
                                g = c1[1] + (c2[1] - c1[1]) * lt
                                b = c1[2] + (c2[2] - c1[2]) * lt
                                a = c1[3] + (c2[3] - c1[3]) * lt
                        else:
                            # Object format with explicit stop keys
                            stops = sorted([(float(k), v) for k, v in gradient.items()])
                            if interpolant <= stops[0][0]:
                                r, g, b, a = parse_hex_color(stops[0][1])
                            elif interpolant >= stops[-1][0]:
                                r, g, b, a = parse_hex_color(stops[-1][1])
                            else:
                                for si in range(len(stops) - 1):
                                    if stops[si][0] <= interpolant <= stops[si + 1][0]:
                                        span = stops[si + 1][0] - stops[si][0]
                                        lt = (interpolant - stops[si][0]) / span if span > 0 else 0.0
                                        c1 = parse_hex_color(stops[si][1])
                                        c2 = parse_hex_color(stops[si + 1][1])
                                        r = c1[0] + (c2[0] - c1[0]) * lt
                                        g = c1[1] + (c2[1] - c1[1]) * lt
                                        b = c1[2] + (c2[2] - c1[2]) * lt
                                        a = c1[3] + (c2[3] - c1[3]) * lt
                                        break

                elif isinstance(color_data, list):
                    rv = self.evaluate_val(color_data[0] if len(color_data) > 0 else 1.0, ctx_p)
                    gv = self.evaluate_val(color_data[1] if len(color_data) > 1 else 1.0, ctx_p)
                    bv = self.evaluate_val(color_data[2] if len(color_data) > 2 else 1.0, ctx_p)
                    av = self.evaluate_val(color_data[3] if len(color_data) > 3 else 1.0, ctx_p)
                    r, g, b, a = srgb2lin(rv), srgb2lin(gv), srgb2lin(bv), av

                elif isinstance(color_data, str) and color_data.startswith("#"):
                    r, g, b, a = parse_hex_color(color_data)

                else:
                    cv = self.evaluate_val(color_data, ctx_p)
                    r, g, b, a = cv, cv, cv, 1.0

                p.color = [r, g, b, a]

                # Update UV
                uv_offset = [0.0, 0.0]
                uv_scale = [1.0, 1.0]
                billboard = self.parser.components.get("minecraft:particle_appearance_billboard")
                if billboard is None:
                    billboard = self.parser.components.get("minecraft:particle_appearance_stretched_billboard", {})
                uv_data = billboard.get("uv", {})
                
                if uv_data:
                    tex_w = self.evaluate_val(uv_data.get("texture_width", 128), ctx_p)
                    tex_h = self.evaluate_val(uv_data.get("texture_height", 128), ctx_p)
                    
                    if "flipbook" in uv_data:
                        fb = uv_data["flipbook"]
                        base_u = self.evaluate_val(fb.get("base_UV", [0, 0])[0], ctx_p)
                        base_v = self.evaluate_val(fb.get("base_UV", [0, 0])[1], ctx_p)
                        size_u = self.evaluate_val(fb.get("size_UV", [1, 1])[0], ctx_p)
                        size_v = self.evaluate_val(fb.get("size_UV", [1, 1])[1], ctx_p)
                        step_u = self.evaluate_val(fb.get("step_UV", [0, 0])[0], ctx_p)
                        step_v = self.evaluate_val(fb.get("step_UV", [0, 0])[1], ctx_p)
                        fps = self.evaluate_val(fb.get("frames_per_second", 1), ctx_p)
                        max_frame = self.evaluate_val(fb.get("max_frame", 1), ctx_p)
                        stretch = fb.get("stretch_to_lifetime", False)
                        loop = fb.get("loop", False)
                        
                        if stretch:
                            progress = p.age / max(0.001, p.lifetime)
                            fb_frame = int(progress * max_frame)
                        else:
                            fb_frame = int(p.age * fps)
                            
                        if loop and max_frame > 0:
                            fb_frame = fb_frame % int(max_frame)
                        else:
                            fb_frame = min(fb_frame, int(max_frame) - 1 if max_frame > 0 else 0)
                            
                        u_px = base_u + fb_frame * step_u
                        v_px = base_v + fb_frame * step_v
                        
                        if tex_w > 0 and tex_h > 0:
                            uv_scale = [size_u / tex_w, size_v / tex_h]
                            uv_offset = [u_px / tex_w, 1.0 - ((v_px + size_v) / tex_h)]
                    elif "uv" in uv_data and "uv_size" in uv_data:
                        u_px = self.evaluate_val(uv_data["uv"][0], ctx_p)
                        v_px = self.evaluate_val(uv_data["uv"][1], ctx_p)
                        su_px = self.evaluate_val(uv_data["uv_size"][0], ctx_p)
                        sv_px = self.evaluate_val(uv_data["uv_size"][1], ctx_p)
                        
                        if tex_w > 0 and tex_h > 0:
                            uv_scale = [su_px / tex_w, sv_px / tex_h]
                            uv_offset = [u_px / tex_w, 1.0 - ((v_px + sv_px) / tex_h)]

                p.uv_offset = uv_offset
                p.uv_scale = uv_scale

                # Evaluate custom direction if lookat_direction is used
                custom_direction_vec = None
                dir_config = self.parser.get_billboard_direction()
                if dir_config and dir_config.get("mode") == "custom":
                    cd = dir_config.get("custom_direction", [0, 0, 1])
                    if isinstance(cd, list) and len(cd) >= 3:
                        cdx = self.evaluate_val(cd[0], ctx_p)
                        cdy = self.evaluate_val(cd[1], ctx_p)
                        cdz = self.evaluate_val(cd[2], ctx_p)
                        custom_direction_vec = mathutils.Vector((cdx, cdy, cdz))
                        if custom_direction_vec.length > 0.0001:
                            custom_direction_vec.normalize()

                # Save history
                p.history[frame] = {
                    'pos': p.position.copy() * self.animation_scale,
                    'scale_x': p.size[0] * self.particle_scale,
                    'scale_y': p.size[1] * self.particle_scale,
                    'color': p.color,
                    'uv_offset': p.uv_offset,
                    'uv_scale': p.uv_scale,
                    'rot_z': math.degrees(p.rotation),
                    'velocity': p.velocity.copy(),
                    'spawn_direction': p.spawn_direction.copy(),
                    'custom_direction': custom_direction_vec,
                }

                # Age
                p.age += self.dt
                p.rotation += p.rotation_rate * self.dt
                if p.age >= p.lifetime:
                    p.active = False
                    
                # Evaluate lifetime events
                if self.lifetime_events:
                    # Timeline events
                    timeline = self.lifetime_events.get("timeline", {})
                    for t_str, event_name in timeline.items():
                        try:
                            t_val = float(t_str)
                            if p.age >= t_val and t_str not in p.fired_timeline_events:
                                p.fired_timeline_events.add(t_str)
                                p.triggered_events.append({
                                    "time": self.anim_time,
                                    "event_name": event_name,
                                    "matrix": mathutils.Matrix.Translation(mathutils.Vector((p.position.x, p.position.z, -p.position.y)))
                                })
                                self.all_triggered_events.append(p.triggered_events[-1])
                        except ValueError:
                            pass
                            
                    # Expiration event
                    if not p.active:
                        expire_event = self.lifetime_events.get("expiration_event")
                        if expire_event:
                            p.triggered_events.append({
                                "time": self.anim_time,
                                "event_name": expire_event,
                                "matrix": mathutils.Matrix.Translation(mathutils.Vector((p.position.x, p.position.z, -p.position.y)))
                            })
                            self.all_triggered_events.append(p.triggered_events[-1])

            self.emitter_age += self.dt
            self.anim_time += self.dt

        return self.particles
