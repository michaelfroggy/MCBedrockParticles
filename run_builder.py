import bpy, sys
sys.path.insert(0, r"c:\Users\MrRob\Downloads\Blender Particles plugin")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='MCBedrockParticles')
bpy.context.scene.mcbedrock_bake_frames = 60
bpy.ops.mcbedrock.import_particle(filepath=r"c:\Users\MrRob\Downloads\Blender Particles plugin\rainbow.particle.json")
emitter = bpy.context.active_object
if emitter:
    children = [c for c in emitter.children if c.type == 'MESH']
    if children:
        p = children[0]
        print('Particle 0 animation data:')
        for f in range(1, 40):
            bpy.context.scene.frame_set(f)
            bpy.context.view_layer.update()
            print(f'Frame {f}: scale={p.scale}')
