import bpy
from .util import *
import bmesh

class SyncMaterialsToActiveOperator(bpy.types.Operator):
    bl_idname = "cat.sync_materials_from_active"
    bl_label = "Sync Materials From Active"
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
            if hasattr(obj.data,"materials"):
                meshes.append(obj)
        source_mat=active_obj.data.materials[0]
        for obj in meshes:
            if obj != active_obj:
                if len(obj.data.materials) == 0:
                    # print("no mat slot")
                    obj.data.materials.append(source_mat)
                elif len(obj.data.materials) > 0:
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
    bl_description = "Turn off shadow and add displacement offset, In Edit Mode remove non-selected faces and set pivot to center of selected faces"  
    bl_options = {'UNDO'}

    def execute(self, context):
        # 如果在EDIT MODE，处理选中顶点
        if context.mode == 'EDIT_MESH':
            # 支持多个object edit mode
            edit_objs = [obj for obj in context.selected_objects if obj.mode == 'EDIT']
            objs_to_process = []
            centers = {}
            prev_selection = {}
            for obj in edit_objs:
                bm = bmesh.from_edit_mesh(obj.data)
                selected_verts = [v for v in bm.verts if v.select]
                if selected_verts:
                    # 记录当前所有object的顶点选择状态
                    for other_obj in edit_objs:
                        if other_obj != obj:
                            other_bm = bmesh.from_edit_mesh(other_obj.data)
                            prev_selection[other_obj.name] = [v.select for v in other_bm.verts]
                            # 取消其它object的所有顶点选择
                            for v in other_bm.verts:
                                v.select = False
                            bmesh.update_edit_mesh(other_obj.data)
                    # 删除未选中的顶点
                    unselected_verts = [v for v in bm.verts if not v.select]
                    bmesh.ops.delete(bm, geom=unselected_verts, context='VERTS')
                    bmesh.update_edit_mesh(obj.data)
                    # 记录中心点
                    center = find_selected_element_center()
                    centers[obj.name] = center
                    objs_to_process.append(obj)
                    # 恢复其它object的顶点选择状态
                    for other_obj in edit_objs:
                        if other_obj != obj and other_obj.name in prev_selection:
                            other_bm = bmesh.from_edit_mesh(other_obj.data)
                            for v, sel in zip(other_bm.verts, prev_selection[other_obj.name]):
                                v.select = sel
                            bmesh.update_edit_mesh(other_obj.data)
                # 如果没有选中顶点则跳过
            # 切换所有edit对象回OBJECT MODE
            bpy.ops.object.mode_set(mode='OBJECT')
            # 设置pivot到选中顶点中心
            for obj in objs_to_process:
                center = centers.get(obj.name)
                if center is not None:
                    set_object_pivot_location(obj, center)

        selected_objs = context.selected_objects

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        count = 0
        for obj in selected_objs:
            if obj.type in {'MESH', 'FONT'}:
                # 关闭投影
                if hasattr(obj, "cycles"):
                    obj.cycles.is_shadow_catcher = False
                if hasattr(obj, "visible_shadow"):
                    obj.visible_shadow = False
                if hasattr(obj, "show_shadows"):
                    obj.display.show_shadows = False

                obj[CUSTOM_NAME] = DECAL_NAME

                # 增加一个displace modifier
                if DISPLACE_MOD not in obj.modifiers:
                    disp_mod = obj.modifiers.new(name=DISPLACE_MOD, type='DISPLACE')
                    disp_mod.strength = 0.002
                count += 1

        self.report({'INFO'}, f"Set {count} object(s) as Decal Object")

        return {"FINISHED"}