import bpy
from .util import *

class SyncMaterialsToActiveOperator(bpy.types.Operator):
    bl_idname = "cat.sync_materials_to_active"
    bl_label = "SyncMaterialsToActive"
    bl_description = "Assign Active Object Material to Selected Objects"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        selected_objs = context.selected_objects
        active_obj = context.active_object
        if len(selected_objs) <= 1 or active_obj is None:
            self.report({'WARNING'}, "No vaild target objects, Need at least 2 selected objects")
            return {"CANCELLED"}

        if len(active_obj.data.materials) ==0:
            self.report({'WARNING'}, "Active object has no material")
            return {"CANCELLED"}
        meshes = []
        for obj in selected_objs:
            if len(obj.data.materials) > 0:
                meshes.append(obj)
        source_mat=active_obj.data.materials[0]
        for obj in meshes:
            if obj != active_obj:
                if len(obj.data.materials) > 0:
                    for i in range(len(obj.data.materials)):
                        obj.data.materials[i] = source_mat

                else:
                    obj.data.materials.append(source_mat)

        
        return {"FINISHED"}





class SetWorkModeOperator(bpy.types.Operator):
    bl_idname = "cat.set_work_mode"
    bl_label = "Set Work Mode"
    bl_options = {'UNDO'}


    def execute(self, context):
        # 接收传递过来的参数
        params = context.scene.cat_params
        work_mode=params.work_mode
        
        if work_mode == 'DEFAULT':
            set_work_mode("BLENDER DEFAULT")
        elif work_mode == 'MODELING':
            set_work_mode("MODELING")
        elif work_mode == 'LIGHTING':
            set_work_mode("LIGHTING")

        self.report({'INFO'}, f"Set work mode to {work_mode}")

        return {"FINISHED"}
    
class SetDecalObjectOperator(bpy.types.Operator):
    bl_idname = "cat.set_decal_object"
    bl_label = "Set Decal Object"
    bl_description = "Turn off shadow and add displacement offset"  
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        # 对于选中的mesh 或者 text 类型的object， 关闭投影， 增加一个displace modifier
        selected_objs = context.selected_objects

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        count=0
        for obj in selected_objs:
            if obj.type in {'MESH', 'FONT'}:
            # 关闭投影
                if hasattr(obj, "cycles"):
                    obj.cycles.is_shadow_catcher = False
                if hasattr(obj, "visible_shadow"):
                    obj.visible_shadow = False
                if hasattr(obj, "show_shadows"):   
                    obj.display.show_shadows = False

                obj[CUSTOM_NAME]=DECAL_NAME

                # 增加一个displace modifier
                if DISPLACE_MOD not in obj.modifiers:
                    disp_mod = obj.modifiers.new(name=DISPLACE_MOD, type='DISPLACE')
                    disp_mod.strength = 0.002
                count+=1


        self.report({'INFO'}, f"Set {count} object(s) as Decal Object")

        return {"FINISHED"}