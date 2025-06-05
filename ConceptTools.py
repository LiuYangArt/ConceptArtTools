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
        elif work_mode == 'LOCALFOG':
            set_work_mode("LOCALFOG")

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
                elif obj.modifiers[DISPLACE_MOD]:
                    disp_mod=obj.modifiers[DISPLACE_MOD]
                if disp_mod:
                    disp_mod.strength = DECAL_OFFSET

                count += 1

        self.report({'INFO'}, f"Set {count} object(s) as Decal Object")

        return {"FINISHED"}
    

def get_material_data_from_obj(obj):
    """Get material data from object"""
    mat_basecolor = None
    mat_roughness = None
    mat_metallic = None
    if obj.type == 'MESH':
        if len(obj.data.materials) > 0:
            mat = obj.data.materials[0]
            if mat:
                mat_basecolor = mat.node_tree.nodes.get("Principled BSDF").inputs[0].default_value
                mat_metallic = mat.node_tree.nodes.get("Principled BSDF").inputs[1].default_value
                mat_roughness = mat.node_tree.nodes.get("Principled BSDF").inputs[2].default_value
                
            else: 
                return None
    return mat_basecolor,mat_metallic,mat_roughness 

DECAL_ATTR_COLOR = "CAT_Decal_Color"
DECAL_ATTR_ROUGHNESS = "CAT_Decal_Roughness"
DECAL_ATTR_METALLIC = "CAT_Decal_Metallic"
def set_material_data_to_obj(obj, mat_basecolor, mat_metallic, mat_roughness):
    if obj.type == 'MESH':
        print("set material data to decal object's attribute")
        #  set material data to decal object's attribute
        print(f" set mat_basecolor: {mat_basecolor},  mat_metallic: {mat_metallic}, mat_roughness: {mat_roughness}")
        
        obj[DECAL_ATTR_COLOR] = mat_basecolor
        obj[DECAL_ATTR_ROUGHNESS] = mat_roughness
        obj[DECAL_ATTR_METALLIC] = mat_metallic
        # 检查object的顶点色属性是否存在
        if DECAL_ATTR_COLOR not in obj.data.attributes:
            obj.data.attributes.new(DECAL_ATTR_COLOR, 'FLOAT_COLOR', 'POINT')
        if DECAL_ATTR_ROUGHNESS not in obj.data.attributes:
            obj.data.attributes.new(DECAL_ATTR_ROUGHNESS, 'FLOAT', 'POINT')
        if DECAL_ATTR_METALLIC not in obj.data.attributes:
            obj.data.attributes.new(DECAL_ATTR_METALLIC, 'FLOAT', 'POINT')
        # 将属性写入所有顶点
        color_attr = obj.data.attributes[DECAL_ATTR_COLOR]
        roughness_attr = obj.data.attributes[DECAL_ATTR_ROUGHNESS]
        metallic_attr = obj.data.attributes[DECAL_ATTR_METALLIC]

        color_list = list(mat_basecolor)
        color_data = color_list * len(color_attr.data)
        color_attr.data.foreach_set(
            "color_srgb", color_data
        )
        roughness_attr.data.foreach_set(
            "value", [mat_roughness] * len(roughness_attr.data)
        )
        metallic_attr.data.foreach_set(
            "value", [mat_metallic] * len(metallic_attr.data)
        )


class MatchMaterialToDecalOperator(bpy.types.Operator):
    bl_idname = "cat.match_material_to_decal"
    bl_label = "Match Material to Decal"
    bl_options = {"UNDO"}
    bl_description = "Match Material to Decal"

    def execute(self, context):
        selected_objs = context.selected_objects
        active_obj = context.active_object
        selected_objs.remove(active_obj)
        source_obj = selected_objs[0]
        if active_obj[CUSTOM_NAME] == DECAL_NAME: # is decal object
            mat_basecolor,  mat_metallic, mat_roughness = get_material_data_from_obj(source_obj)
            if mat_basecolor is None:
                self.report({'WARNING'}, "Source object has no material")
                return {"CANCELLED"}
            for i in mat_basecolor:
                print(i)
            print(f"mat_basecolor: {mat_basecolor},  mat_metallic: {mat_metallic}, mat_roughness: {mat_roughness}") 
            #save material data to decal object's attribute, basecolor to vertex color attribute, roughness and metallic to float attribute
            set_material_data_to_obj(active_obj, mat_basecolor,mat_metallic, mat_roughness )

            for i in active_obj[DECAL_ATTR_COLOR]:
                print(i)
        else: 
            self.report({'WARNING'}, "Active object is not a Decal Object")
            return {"CANCELLED"}

        self.report({'INFO'}, f"Match Material to Decal Finished")

        return {"FINISHED"}
    def invoke(self, context, event):
        selected_objs = context.selected_objects
        active_obj = context.active_object
        
        if len(selected_objs) != 2: # only two objects are selected
            self.report({'WARNING'}, "Please select two objects")
            return {"CANCELLED"}
        # if active_obj[CUSTOM_NAME] != DECAL_NAME:
        #     self.report({'WARNING'}, "Active object is not a Decal Object")
        return self.execute(context)

