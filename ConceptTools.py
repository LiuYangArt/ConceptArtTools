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
def break_link_from_assetlib(object):
    obj_collection = object.users_collection[0]
    unlinked_mesh =object.copy()
    unlinked_mesh.data = object.data.copy()
    obj_collection.objects.link(unlinked_mesh)
    mesh_data=object.data
    mesh_name=object.name
    bpy.data.objects.remove(object)
    bpy.data.meshes.remove(mesh_data)
    unlinked_mesh.name = mesh_name
    return unlinked_mesh
class SetDecalObjectOperator(bpy.types.Operator):
    bl_idname = "cat.set_decal_object"
    bl_label = "Set Decal Object"
    bl_description = "Turn off shadow and add displacement offset, In Edit Mode remove non-selected faces and set pivot to center of selected faces"  
    bl_options = {"REGISTER", "UNDO"}

    offset_distance: bpy.props.FloatProperty(name="Offset Distance", default=0.008, min=0.0, max=1.0, step=1, precision=2)
    vertexcolor: bpy.props.FloatVectorProperty(
        name="Bake Color Picker",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5, 0.5),
    )
    def execute(self, context):
        # 如果在EDIT MODE，处理选中顶点
        print(self.offset_distance)
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
                obj=break_link_from_assetlib(obj)
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
                    disp_mod.strength = self.offset_distance

                color_attr_name = get_vertex_color_attribute_name(obj)
                if color_attr_name is None:
                    color_attr_name = DECAL_ATTR_COLOR
                set_object_vertexcolor(obj, self.vertexcolor,color_attr_name)
                count += 1

        self.report({'INFO'}, f"Set {count} object(s) as Decal Object")

        return {"FINISHED"}
    def invoke(self, context, event):
        return self.execute(context)
    

def get_material_data_from_obj(obj):
    """Get material data from object"""
    mat_basecolor = None
    mat_roughness = None
    mat_metallic = None
    if obj.type == 'MESH':
        if len(obj.data.materials) > 0:
            mat = obj.data.materials[0]
            if mat:
                principled = mat.node_tree.nodes.get("Principled BSDF")
                if principled:
                    # 通过input的名字获取数据
                    mat_basecolor = principled.inputs["Base Color"].default_value
                    mat_metallic = principled.inputs["Metallic"].default_value
                    mat_roughness = principled.inputs["Roughness"].default_value
                else:
                    print("No principled node found in material")
                    return None
                
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
        source_obj = active_obj
        for target_obj in selected_objs:
            if target_obj[CUSTOM_NAME] == DECAL_NAME: # is decal object
                mat_data=get_material_data_from_obj(source_obj)
                if mat_data is None: 
                    self.report({'ERROR'}, "Source object has no principled BSDF")
                    return {"CANCELLED"}
                else:
                    mat_basecolor,  mat_metallic, mat_roughness = mat_data
                if mat_basecolor is None:
                    self.report({'WARNING'}, "Source object has no material")
                    return {"CANCELLED"}
                for i in mat_basecolor:
                    print(i)
                print(f"mat_basecolor: {mat_basecolor},  mat_metallic: {mat_metallic}, mat_roughness: {mat_roughness}") 
                #save material data to decal object's attribute, basecolor to vertex color attribute, roughness and metallic to float attribute
                set_material_data_to_obj(active_obj, mat_basecolor,mat_metallic, mat_roughness )

            else: 
                self.report({'WARNING'}, "Active object is not a Decal Object")
                return {"CANCELLED"}

        self.report({'INFO'}, f"Match Material to Decal Finished")

        return {"FINISHED"}
    def invoke(self, context, event):
        selected_objs = context.selected_objects
        active_obj = context.active_object
        
        if len(selected_objs) < 2: # only two objects are selected
            self.report({'WARNING'}, "Please select at least two objects")
            return {"CANCELLED"}
        # if active_obj[CUSTOM_NAME] != DECAL_NAME:
        #     self.report({'WARNING'}, "Active object is not a Decal Object")
        return self.execute(context)

def get_vertex_color_from_obj(obj)->list:
    if obj.type == 'MESH':
        # 使用第一个 color attribute
        color_attr = None
        for attr in obj.data.color_attributes:
            print(attr.name , attr)
            if attr.domain in {'POINT', 'CORNER'}:
                color_attr = obj.data.attributes[attr.name]
            break
        if color_attr:
            color_data = color_attr.data
            color_list = []
            for i in color_data:
                # 支持 COLOR 和 BYTE_COLOR 两种类型
                if hasattr(i, "color_srgb"):
                    color_list.append(i.color_srgb)
                elif hasattr(i, "color"):
                    color_list.append(i.color)
                elif hasattr(i, "vertex_colors"):
                    color_list.append(i.color)
                else:
                    color_list.append(None)
            if color_list:
                color = [
                sum(c[i] for c in color_list) / len(color_list)
                for i in range(len(color_list[0]))
                ]
                return color
        else:
            return None
def get_vertex_color_attribute_name(obj)->str:
    if obj.type == 'MESH':
        # 使用第一个 color attribute
        color_attr = None
        for attr in obj.data.color_attributes:
            print(attr.name , attr)
            if attr.domain in {'POINT', 'CORNER'}:
                color_attr = obj.data.attributes[attr.name]
            break
        if color_attr:
            return color_attr.name
        else:
            return None
        
def set_object_vertexcolor(target_object, color: tuple, vertexcolor_name: str) -> None:
    """设置顶点色"""
    color = tuple(color)
    # print(current_mode)
    if target_object.type == "MESH":
        mesh = target_object.data
        if vertexcolor_name in mesh.color_attributes:
            color_attribute = mesh.color_attributes.get(vertexcolor_name)
        else:
            color_attribute = mesh.color_attributes.new(name=vertexcolor_name, type='FLOAT_COLOR', domain='POINT')
        # 设置所有顶点色
        color_data = list(color) * len(color_attribute.data)
        color_attribute.data.foreach_set("color_srgb", color_data)
        # 设为active
        mesh.attributes.active_color = color_attribute


class CopyVertexColorFromActiveOperator(bpy.types.Operator):
    bl_idname = "cat.copy_vertex_color_from_active"
    bl_label = "Copy Vertex Color From Active"
    bl_options = {"UNDO"}
    bl_description = "Copy Vertex Color From Active"

    def execute(self, context):
        selected_objs = context.selected_objects
        active_obj = context.active_object
        selected_objs.remove(active_obj)
        source_obj = active_obj
        color=get_vertex_color_from_obj(source_obj)
        # atribute_name = DECAL_ATTR_COLOR
        if color is None: 
            self.report({'ERROR'}, "Source object has no vertex color")
            return {"CANCELLED"}
        for target_obj in selected_objs:
            color_attr_name = get_vertex_color_attribute_name(target_obj)
            if color_attr_name is None:
                color_attr_name = DECAL_ATTR_COLOR
            set_object_vertexcolor(target_obj, color, color_attr_name)


        self.report({'INFO'}, f"Copied Vertex Color From Active Finished")

        return {"FINISHED"}
    def invoke(self, context, event):
        selected_objs = context.selected_objects
        
        if len(selected_objs) < 2: # only two objects are selected
            self.report({'WARNING'}, "Please select at least two objects")
            return {"CANCELLED"}
        # if active_obj[CUSTOM_NAME] != DECAL_NAME:
        #     self.report({'WARNING'}, "Active object is not a Decal Object")
        return self.execute(context)