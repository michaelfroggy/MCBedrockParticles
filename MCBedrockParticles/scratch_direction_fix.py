import sys

file_path = r"c:\Users\MrRob\Downloads\Blender Particles plugin\MCBedrockParticles\simulator.py"
with open(file_path, "r") as f:
    content = f.read()

old_direction_logic = """        direction_mode = self.shape_data.get("direction", "outwards")
        if direction_mode == "outwards":
            # Outwards is ALWAYS from the emitter origin (0,0,0) to the absolute particle spawn position
            direction = offset.normalized() if offset.length > 0 else direction
        elif direction_mode == "inwards":
            direction = -offset.normalized() if offset.length > 0 else direction"""

new_direction_logic = """        direction_mode = self.shape_data.get("direction", "outwards")
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
                direction = custom_dir.normalized()"""

content = content.replace(old_direction_logic, new_direction_logic)

with open(file_path, "w") as f:
    f.write(content)
print("Added explicit array direction support.")
