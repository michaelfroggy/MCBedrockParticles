import sys

builder_path = r"c:\Users\MrRob\Downloads\Blender Particles plugin\MCBedrockParticles\builder.py"
with open(builder_path, "r") as f:
    b_content = f.read()

# Add mc_alpha init
b_content = b_content.replace(
    'p_obj["uv_scale_y"] = 1.0',
    'p_obj["uv_scale_y"] = 1.0\n        p_obj["mc_alpha"] = 1.0'
)

# Make color linear, keep uv and hide constant
b_content = b_content.replace(
    'if data_path == "color" or data_path.startswith(\'["uv_\') or data_path.startswith(\'hide_\'):',
    'if data_path.startswith(\'["uv_\') or data_path.startswith(\'hide_\'):'
)

# Apply fcurve for mc_alpha
b_content = b_content.replace(
    '        apply_fcurve("color", 3, colors_a)',
    '        apply_fcurve("color", 3, colors_a)\n        apply_fcurve(\'["mc_alpha"]\', 0, colors_a)'
)

with open(builder_path, "w") as f:
    f.write(b_content)


materials_path = r"c:\Users\MrRob\Downloads\Blender Particles plugin\MCBedrockParticles\materials.py"
with open(materials_path, "r") as f:
    m_content = f.read()

# Replace alpha linking to use mc_alpha custom property
old_alpha_link = """        if 'Alpha' in obj_info.outputs:
            links.new(obj_info.outputs['Alpha'], math_node.inputs[1])
        else:
            math_node.inputs[1].default_value = 1.0"""

new_alpha_link = """        # Use an Attribute node to read mc_alpha since Object Info drops alpha
        attr_alpha = nodes.new('ShaderNodeAttribute')
        attr_alpha.attribute_type = 'OBJECT'
        attr_alpha.attribute_name = "mc_alpha"
        attr_alpha.location = (-300, 50)
        links.new(attr_alpha.outputs['Fac'], math_node.inputs[1])"""

m_content = m_content.replace(old_alpha_link, new_alpha_link)

with open(materials_path, "w") as f:
    f.write(m_content)

print("Applied alpha fix!")
