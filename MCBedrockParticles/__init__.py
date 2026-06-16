bl_info = {
    "name": "MC Bedrock Particles",
    "author": "michaelfroggy",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > MC Particles",
    "description": "Import and bake Minecraft Bedrock & Java particles.",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}


try:
    import bpy
    from bpy.types import AddonPreferences
    from bpy_extras.io_utils import ImportHelper
except ImportError:
    bpy = None
    ImportHelper = object

if "builder" in locals():
    import importlib
    importlib.reload(materials)
    importlib.reload(molang)
    importlib.reload(molang_parser)
    importlib.reload(parser)
    importlib.reload(java_parser)
    importlib.reload(simulator)
    importlib.reload(builder)
else:
    from . import materials
    from . import molang
    from . import molang_parser
    from . import parser
    from . import java_parser
    from . import simulator
    from . import builder



class MCBEDROCK_OT_import_particle(bpy.types.Operator, ImportHelper):
    """Import a Minecraft Bedrock or Java Particle JSON file"""
    bl_idname = "mcbedrock.import_particle"
    bl_label = "Import Particle JSON"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,
    )

    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    manual_texture: bpy.props.StringProperty(
        name="Manual Texture Override",
        description="(Optional) Manually select a .png texture to use instead of auto-resolving from the JSON",
        subtype='FILE_PATH',
        default="",
    )

    force_loop: bpy.props.BoolProperty(
        name="Force Endless Loop",
        description="Override 'once' lifetime and force the particle to loop continuously",
        default=False,
    )

    def execute(self, context):
        import os
        try:
            tex_override = bpy.path.abspath(self.manual_texture) if self.manual_texture else ""
            warnings = []
            
            for f in self.files:
                filepath = os.path.join(self.directory, f.name)
                
                result = builder.build_particle_system(
                    context, 
                    filepath, 
                    texture_override=tex_override,
                    spawn_offset=(0.0, 0.0, 0.0),
                    force_loop=self.force_loop
                )
                
                emitter = context.active_object
                if emitter:
                    emitter["mcbedrock_filepath"] = filepath
                    emitter["mcbedrock_texture"] = tex_override
                    emitter["mcbedrock_force_loop"] = self.force_loop
                    
                    # Apply current live slider values to the newly created active object
                    update_scales(emitter, context)
                
                if result and result.get("warning"):
                    warnings.append(f"{f.name}: {result['warning']}")
                    
            if warnings:
                self.report({'WARNING'}, " | ".join(warnings))
            else:
                self.report({'INFO'}, f"Successfully imported {len(self.files)} particles")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import particles: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "manual_texture")
        layout.label(text="Leave blank to auto-resolve from resource pack.", icon='INFO')
        layout.separator()
        layout.prop(self, "force_loop")


class MCBEDROCK_OT_set_resource_pack(bpy.types.Operator, ImportHelper):
    """Select the root folder of your resource pack (Bedrock or Java)"""
    bl_idname = "mcbedrock.set_resource_pack"
    bl_label = "Set Resource Pack Path"
    bl_options = {'REGISTER'}

    filter_glob: bpy.props.StringProperty(
        default="*.*",
        options={'HIDDEN'},
        maxlen=255,
    )

    directory: bpy.props.StringProperty(
        subtype='DIR_PATH',
    )

    def execute(self, context):
        import os
        folder = os.path.dirname(self.filepath) if self.filepath else self.directory
        context.scene.mcbedrock_resource_pack_path = folder
        self.report({'INFO'}, f"Resource pack set to: {folder}")
        return {'FINISHED'}


class MCBEDROCK_OT_install_vanilla_pack(bpy.types.Operator, ImportHelper):
    """Install the downloaded bedrock-samples.zip permanently into the addon"""
    bl_idname = "mcbedrock.install_vanilla_pack"
    bl_label = "Install Vanilla ZIP"
    bl_options = {'REGISTER'}

    filter_glob: bpy.props.StringProperty(
        default="*.zip",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        import os
        import zipfile
        
        if not self.filepath or not self.filepath.endswith('.zip'):
            self.report({'ERROR'}, "Please select a .zip file")
            return {'CANCELLED'}
            
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        dest_dir = os.path.join(addon_dir, "vanilla_pack")
        
        try:
            # Create the vanilla_pack directory if it doesn't exist
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
                
            self.report({'INFO'}, "Extracting ZIP, this may take a moment...")
            # Extract the zip
            with zipfile.ZipFile(self.filepath, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
                
            self.report({'INFO'}, "Vanilla pack installed permanently!")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to install zip: {e}")
            return {'CANCELLED'}

class MCBEDROCK_OT_set_texture(bpy.types.Operator, ImportHelper):
    """Manually pick a .png texture to apply to the selected particle emitter"""
    bl_idname = "mcbedrock.set_texture"
    bl_label = "Set Particle Texture"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.jpg;*.jpeg",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        import os
        from .materials import create_particle_material

        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected")
            return {'CANCELLED'}

        # Find the particle instance object
        target = None
        if obj.name.startswith("Emitter_"):
            for child in obj.children:
                if child.type == 'MESH':
                    target = child
                    break

        if target is None:
            # Maybe the user selected the particle plane directly
            if obj.type == 'MESH' and obj.name.startswith("Particle_"):
                target = obj
            else:
                self.report({'ERROR'}, "Select an emitter or a Particle_ mesh object")
                return {'CANCELLED'}

        if not os.path.isfile(self.filepath):
            self.report({'ERROR'}, f"File not found: {self.filepath}")
            return {'CANCELLED'}

        create_particle_material(target, self.filepath, "particles_alpha")
        self.report({'INFO'}, f"Applied texture: {os.path.basename(self.filepath)}")
        return {'FINISHED'}


class MCBEDROCK_OT_attach_to_bone(bpy.types.Operator):
    """Attach the selected MC particle emitter to a specific armature bone"""
    bl_idname = "mcbedrock.attach_to_bone"
    bl_label = "Attach Emitter to Bone"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.name.startswith("Emitter_"):
            self.report({'ERROR'}, "Select an Emitter_ object first")
            return {'CANCELLED'}

        armature = context.scene.mcbedrock_target_armature
        bone_name = context.scene.mcbedrock_target_bone

        if not armature:
            self.report({'ERROR'}, "No armature selected")
            return {'CANCELLED'}

        if not bone_name:
            self.report({'ERROR'}, "No bone name specified")
            return {'CANCELLED'}

        if armature.type != 'ARMATURE' or bone_name not in armature.data.bones:
            self.report({'ERROR'}, f"Bone '{bone_name}' not found in armature")
            return {'CANCELLED'}

        # Remove any existing Child Of constraints from previous attachments
        for c in list(obj.constraints):
            if c.type == 'CHILD_OF':
                obj.constraints.remove(c)

        child_of = obj.constraints.new(type='CHILD_OF')
        child_of.target = armature
        child_of.subtarget = bone_name
        child_of.use_scale_x = False
        child_of.use_scale_y = False
        child_of.use_scale_z = False

        # Set inverse to neutralize the parent transform at bind pose
        context.view_layer.objects.active = obj
        bpy.ops.constraint.childof_set_inverse(constraint=child_of.name, owner='OBJECT')

        self.report({'INFO'}, f"Attached to {armature.name}/{bone_name}")
        return {'FINISHED'}


class MCBEDROCK_OT_bake_world_space(bpy.types.Operator):
    """Re-bakes the particle system using the Emitter's animation to create World Space trails"""
    bl_idname = "mcbedrock.bake_world_space"
    bl_label = "Re-Bake Simulation (World Space Trails)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os
        from . import builder
        
        obj = context.active_object
        emitter = obj if obj and obj.name.startswith("Emitter_") else (obj.parent if obj and obj.parent and obj.parent.name.startswith("Emitter_") else None)
        
        if not emitter:
            self.report({'ERROR'}, "Select an Emitter first")
            return {'CANCELLED'}
            
        filepath = emitter.get("mcbedrock_filepath")
        if not filepath or not os.path.isfile(filepath):
            self.report({'ERROR'}, "Original particle JSON not found! Cannot re-bake.")
            return {'CANCELLED'}
            
        tex_override = emitter.get("mcbedrock_texture", "")
        force_loop = emitter.get("mcbedrock_force_loop", False)
        
        # Save Emitter properties
        anim_scale = emitter.mcbedrock_animation_scale
        part_scale = emitter.mcbedrock_particle_scale
        speed_scale = emitter.mcbedrock_speed_scale
        density = emitter.mcbedrock_density
        tint = emitter.mcbedrock_color_tint[:]
        
        # We need to pass the Emitter object itself to the builder so it can read its F-curves
        result = builder.build_particle_system(
            context, 
            filepath, 
            texture_override=tex_override,
            spawn_offset=(0.0, 0.0, 0.0),
            force_loop=force_loop,
            existing_emitter=emitter
        )
        
        if result and result.get("warning"):
            self.report({'WARNING'}, result["warning"])
        else:
            self.report({'INFO'}, "Successfully re-baked particles in World Space!")
            
        # Re-apply live scales
        update_scales(emitter, context)
            
        return {'FINISHED'}

class MCBEDROCK_PT_panel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "MC Particles"
    bl_idname = "MCBEDROCK_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MC Particles'

    def draw(self, context):
        layout = self.layout

        # Resource Pack section
        box = layout.box()
        box.label(text="Resource Pack", icon='FILE_FOLDER')
        rp = context.scene.mcbedrock_resource_pack_path
        if rp:
            row = box.row()
            row.label(text=rp, icon='CHECKMARK')
        else:
            box.label(text="(not set)", icon='ERROR')
        box.operator("mcbedrock.set_resource_pack", icon='FILEBROWSER')
        
        box.separator()
        op = box.operator("wm.url_open", text="1. Download Vanilla Textures", icon='URL')
        op.url = "https://github.com/Mojang/bedrock-samples/releases/latest"
        
        box.operator("mcbedrock.install_vanilla_pack", text="2. Install Downloaded ZIP", icon='FILE_ARCHIVE')

        layout.separator()

        box2 = layout.box()
        box2.label(text="Live Properties (Applies to Selected)", icon='VIEWZOOM')
        
        obj = context.active_object
        emitter = obj if obj and obj.name.startswith("Emitter_") else (obj.parent if obj and obj.parent and obj.parent.name.startswith("Emitter_") else None)
        
        if emitter:
            row_scale = box2.row()
            row_scale.prop(emitter, "mcbedrock_animation_scale", text="Animation Scale")
            row_scale.prop(emitter, "mcbedrock_particle_scale", text="Particle Size")

            row_density = box2.row()
            row_density.prop(emitter, "mcbedrock_speed_scale", text="Simulation Speed")
            row_density.prop(emitter, "mcbedrock_density", text="Density")

            box2.prop(emitter, "mcbedrock_color_tint", text="Color Tint")
            
            box2.separator()
            box2.operator("mcbedrock.bake_world_space", text="Re-Bake Simulation (World Space Trails)", icon='FILE_REFRESH')
        else:
            box2.label(text="Select an Emitter to edit its live properties.", icon='INFO')

        layout.separator()

        box2 = layout.box()
        box2.label(text="Import New", icon='IMPORT')
        box2.prop(context.scene, "mcbedrock_bake_frames", text="Bake Duration (Frames)")
        box2.operator("mcbedrock.import_particle", text="Import Particle JSON", icon='PARTICLES')

        layout.separator()

        # Texture tools section
        box3 = layout.box()
        box3.label(text="Texture Tools", icon='TEXTURE')
        box3.operator("mcbedrock.set_texture", text="Set Particle Texture", icon='IMAGE_DATA')
        box3.label(text="Select an emitter, then pick a .png", icon='INFO')

        layout.separator()

        # Bone Attachment section
        box_bone = layout.box()
        box_bone.label(text="Bone Attachment", icon='BONE_DATA')
        box_bone.prop(context.scene, "mcbedrock_target_armature", text="Armature")
        box_bone.prop(context.scene, "mcbedrock_target_bone", text="Bone")
        box_bone.operator("mcbedrock.attach_to_bone", text="Attach Selected Emitter", icon='CONSTRAINT_BONE')



from . import updater

class MCBEDROCK_OT_check_update(bpy.types.Operator):
    """Check GitHub for updates"""
    bl_idname = "mcbedrock.check_update"
    bl_label = "Check for Updates"
    
    def execute(self, context):
        current_version = bl_info["version"]
        has_update, latest_version, url_or_msg = updater.check_for_update(current_version)
        
        if has_update:
            self.report({'INFO'}, f"Update found! Downloading v{latest_version[0]}.{latest_version[1]}.{latest_version[2]}...")
            success, msg = updater.install_update(url_or_msg)
            if success:
                self.report({'INFO'}, msg)
            else:
                self.report({'ERROR'}, msg)
        else:
            self.report({'INFO'}, url_or_msg)
            
        return {'FINISHED'}

class MCBEDROCK_preferences(AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text=f"Current Version: {bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}")
        row.operator("mcbedrock.check_update", icon='FILE_REFRESH')

classes = (
    MCBEDROCK_OT_check_update,
    MCBEDROCK_preferences,
    MCBEDROCK_OT_import_particle,
    MCBEDROCK_OT_set_resource_pack,
    MCBEDROCK_OT_install_vanilla_pack,
    MCBEDROCK_OT_set_texture,
    MCBEDROCK_OT_attach_to_bone,
    MCBEDROCK_PT_panel,
)


def update_scales(self, context):
    emitter = self
    if not emitter: return
    
    anim_val = max(0.001, emitter.mcbedrock_animation_scale)
    emitter.scale = (anim_val, anim_val, anim_val)
    
    p_val = emitter.mcbedrock_particle_scale
    delta = p_val / anim_val
    
    speed_val = max(0.001, emitter.mcbedrock_speed_scale)
    nla_scale = 1.0 / speed_val
    
    density_val = max(0.0, min(1.0, emitter.mcbedrock_density))
    
    # Particles might be unparented (World Space). Find them via the collection.
    group_col = emitter.users_collection[0] if emitter.users_collection else None
    if group_col:
        mesh_children = [c for c in group_col.objects if c.name.startswith("Particle_") and c.type == 'MESH']
    else:
        mesh_children = [c for c in emitter.children if c.type == 'MESH']
        
    active_count = int(len(mesh_children) * density_val)
    
    tint = emitter.mcbedrock_color_tint
    mat_updated = False
    
    for i, child in enumerate(mesh_children):
        # Apply density by scaling excess particles to 0
        if i >= active_count:
            child.delta_scale = (0.0, 0.0, 0.0)
        else:
            child.delta_scale = (delta, delta, 1.0)
            
        # Apply speed scale
        if child.animation_data and child.animation_data.nla_tracks:
            for track in child.animation_data.nla_tracks:
                for strip in track.strips:
                    strip.scale = nla_scale
                    
        # Apply color tint (only need to update the material once since it's shared)
        if not mat_updated and child.data.materials:
            mat = child.data.materials[0]
            if mat and mat.use_nodes:
                tint_node = mat.node_tree.nodes.get("Global_Tint")
                if tint_node:
                    tint_node.inputs['Color2'].default_value = (tint[0], tint[1], tint[2], tint[3])
            mat_updated = True
            
    # Force depsgraph update so NLA speed scales and material changes reflect instantly in viewport
    context.view_layer.update()

def register():
    if bpy:
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.mcbedrock_resource_pack_path = bpy.props.StringProperty(
            name="Resource Pack Path",
            description="Path to Bedrock resource pack (for texture resolution)",
            default="",
            subtype='DIR_PATH'
        )
        bpy.types.Scene.mcbedrock_bake_frames = bpy.props.IntProperty(
            name="Bake Duration",
            description="Frames to simulate",
            default=1000,
            min=1
        )

        bpy.types.Object.mcbedrock_particle_scale = bpy.props.FloatProperty(
            name="Particle Size Multiplier",
            description="Scales the size of each individual particle plane dynamically",
            default=1.0,
            min=0.001,
            update=update_scales
        )
        bpy.types.Object.mcbedrock_animation_scale = bpy.props.FloatProperty(
            name="Animation Scale Multiplier",
            description="Scales the overall motion/spawn radius of the particle system dynamically",
            default=1.0,
            min=0.001,
            update=update_scales
        )
        bpy.types.Object.mcbedrock_speed_scale = bpy.props.FloatProperty(
            name="Simulation Speed",
            description="Speeds up or slows down the particle animation dynamically",
            default=1.0,
            min=0.001,
            update=update_scales
        )
        bpy.types.Object.mcbedrock_density = bpy.props.FloatProperty(
            name="Density",
            description="Percentage of particles to show (0.0 to 1.0)",
            default=1.0,
            min=0.0,
            max=1.0,
            subtype='FACTOR',
            update=update_scales
        )
        bpy.types.Object.mcbedrock_color_tint = bpy.props.FloatVectorProperty(
            name="Color Tint",
            description="Multiplies the color of the particles dynamically",
            subtype='COLOR',
            size=4,
            default=(1.0, 1.0, 1.0, 1.0),
            min=0.0, max=1.0,
            update=update_scales
        )
        bpy.types.Scene.mcbedrock_target_armature = bpy.props.PointerProperty(
            name="Target Armature",
            type=bpy.types.Object,
            description="Armature to attach the emitter to",
            poll=lambda self, obj: obj.type == 'ARMATURE'
        )
        bpy.types.Scene.mcbedrock_target_bone = bpy.props.StringProperty(
            name="Target Bone",
            description="Bone name to attach the emitter to",
            default=""
        )

def unregister():
    if bpy:
        for cls in reversed(classes):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
        if hasattr(bpy.types.Object, "mcbedrock_particle_scale"):
            del bpy.types.Object.mcbedrock_particle_scale
        if hasattr(bpy.types.Object, "mcbedrock_animation_scale"):
            del bpy.types.Object.mcbedrock_animation_scale
        if hasattr(bpy.types.Object, "mcbedrock_speed_scale"):
            del bpy.types.Object.mcbedrock_speed_scale
        if hasattr(bpy.types.Object, "mcbedrock_density"):
            del bpy.types.Object.mcbedrock_density
        if hasattr(bpy.types.Object, "mcbedrock_color_tint"):
            del bpy.types.Object.mcbedrock_color_tint
        if hasattr(bpy.types.Scene, "mcbedrock_resource_pack_path"):
            del bpy.types.Scene.mcbedrock_resource_pack_path
        if hasattr(bpy.types.Scene, "mcbedrock_bake_frames"):
            del bpy.types.Scene.mcbedrock_bake_frames
        if hasattr(bpy.types.Scene, "mcbedrock_target_armature"):
            del bpy.types.Scene.mcbedrock_target_armature
        if hasattr(bpy.types.Scene, "mcbedrock_target_bone"):
            del bpy.types.Scene.mcbedrock_target_bone

if __name__ == "__main__":
    register()
