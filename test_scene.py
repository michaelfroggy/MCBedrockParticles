import bpy
emitters = [obj.name for obj in bpy.context.scene.objects if obj.name.startswith('Emitter_')]
materials = [mat.name for mat in bpy.data.materials if 'Particle' in mat.name]
print('Emitters:', emitters)
print('Materials:', materials)
