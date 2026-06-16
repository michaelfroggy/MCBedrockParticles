import json
import sys
import os

from simulator import BedrockSimulator

json_data = """{
    "format_version": "1.10.0",
    "particle_effect": {
        "description": {
            "identifier": "spark:ilum_blizzard",
            "basic_render_parameters": {
                "material": "particles_blend",
                "texture": "textures/spark/particle/weather/blizzard"
            }
        },
        "curves": {
            "variable.opacity": {
                "type": "catmull_rom",
                "input": "v.particle_age",
                "horizontal_range": "v.particle_lifetime",
                "nodes": [-1.19, 0, 1, 0, -0.98]
            }
        },
        "components": {
            "minecraft:emitter_rate_steady": {
                "spawn_rate": 60,
                "max_particles": 1000
            },
            "minecraft:emitter_lifetime_once": {
                "active_time": 0.1
            },
            "minecraft:emitter_shape_disc": {
                "offset": [0, "math.random(2, 22)", -20],
                "radius": 40,
                "direction": "outwards"
            },
            "minecraft:particle_lifetime_expression": {
                "max_lifetime": "math.random(4, 7)"
            },
            "minecraft:particle_initial_spin": {
                "rotation": "math.random(-120, 120)",
                "rotation_rate": "math.random(-5, 5)"
            },
            "minecraft:particle_initial_speed": 0,
            "minecraft:particle_motion_dynamic": {
                "linear_acceleration": ["math.random(-10, 10)", -3, "math.random(-10, 26) * 2*(1+math.sin(v.particle_age*300))"],
                "linear_drag_coefficient": 1.2
            },
            "minecraft:particle_appearance_billboard": {
                "size": ["2.2 + v.particle_random_1*2", "2.2 + v.particle_random_1*2 + (v.particle_random_2-0.5) * 0.2"],
                "facing_camera_mode": "rotate_xyz",
                "uv": {
                    "texture_width": 64,
                    "texture_height": 64,
                    "uv": ["math.floor(v.particle_random_3*2) * 32", "math.floor(v.particle_random_4*2) * 32"],
                    "uv_size": [32, 32]
                }
            },
            "minecraft:particle_motion_collision": {
                "collision_radius": 0.01
            },
            "minecraft:particle_appearance_tinting": {
                "color": [1, 1, 1, "variable.opacity"]
            }
        }
    }
}"""

with open("test_blizzard.json", "w") as f:
    f.write(json_data)

sim = BedrockSimulator("test_blizzard.json")
sim.simulate(100, 24)

print(f"Spawned {len(sim.particles)} particles")
for i in range(min(3, len(sim.particles))):
    p = sim.particles[i]
    print(f"Particle {p.id}:")
    print(f"  Start: {p.spawn_frame}, End: {p.death_frame}")
    print(f"  Frame {p.spawn_frame} color: {p.history[p.spawn_frame]['color']}")
    mid_frame = (p.spawn_frame + p.death_frame) // 2
    print(f"  Frame {mid_frame} color: {p.history[mid_frame]['color']}")
    print(f"  Frame {p.death_frame-1} color: {p.history[p.death_frame-1]['color']}")
    print(f"  Pos: {p.history[mid_frame]['pos']}")
