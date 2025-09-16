import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup
from .util import DEFAULT_IO_TEMP_DIR

def run_set_work_mode_op(self, context):
    """当ui参数改变时，运行对应的operator"""
    bpy.ops.cat.set_work_mode("INVOKE_DEFAULT")


def run_import_json_op(self, context):
    """当ui参数改变时，运行对应的operator"""
    bpy.ops.cat.import_unreal_scene("INVOKE_DEFAULT")


class UIParams(PropertyGroup):
    """UI参数"""

    work_mode: bpy.props.EnumProperty(
        name="Set View Mode",
        items=[
            ("DEFAULT", "Blender Default", ""),
            ("MODELING", "Modeling Mode", ""),
            ("LIGHTING", "Lighting Mode", ""),
            ("LOCALFOG", "LocalFog Mode", ""),
        ],
        default="DEFAULT",
        # 执行function， 运行对应的operator
        update=run_set_work_mode_op,
    )

    ubio_json_path: StringProperty(
        name="UBIO JSON Path",
        description="UBIO JSON文件路径",
        default=DEFAULT_IO_TEMP_DIR + "*.json",
        maxlen=1024,
        subtype="FILE_PATH",
        options={'HIDDEN'},
        update=run_import_json_op,
        
)

class InstancedCollectionToolPanel(bpy.types.Panel):
    bl_idname = "CAT_PT_tool_panel"
    bl_label = "ConceptArtTools"
    bl_category = "CAT"  # Custom tab name
    bl_space_type = "VIEW_3D"  # Space type where the panel will be displayed
    bl_region_type = "UI"
    bl_order = 0

    def draw(self, context):
        parameters = context.scene.cat_params
        layout = self.layout
        box = layout.box()
        box_column = box.column()
        box_column.label(text="Plasticity Group Instance")

        box_column.operator("cat.make_mesh_group", icon="OUTLINER_OB_GROUP_INSTANCE")

        box_column.operator("cat.find_source_group", icon="VIEWZOOM")

        box_column.operator("cat.reset_pivot", icon="EMPTY_ARROWS")
        box_column.operator("cat.realize_meshgroup", icon="OBJECT_DATA")
        box_column.operator("cat.add_custom_axis", icon="ADD")
        box_column.operator("cat.apply_meshgroup", icon="MESH_DATA")
        box_column.operator("cat.isolate_group", icon="VIEWZOOM")

        # box_column.operator(
        #     "object.refacet_and_wait", icon="ADD")

        box_column.separator()
        box_column.label(text="Concept Utilities")
        # box_column.separator()
        box_column.operator("cat.sync_materials_from_active", icon="MATERIAL")
        box_column.operator("cat.set_decal_object", icon="MOD_DISPLACE")
        box_column.operator("cat.match_material_to_decal", icon="COPY_ID")
        # box_column.operator("cat.snap_transform", icon="SNAP_GRID")
        # box_column.operator("cat.copy_vertex_color_from_active", icon="COPYDOWN")
        
        
        box_column.prop(parameters, "work_mode", text="Work Mode")

        box_column.operator("cat.organize_lights_and_cameras", icon="LIGHT")
        box_column.operator("cat.colorize_collection_objects", icon="OUTLINER_COLLECTION")
        

        box_column.separator()
        box_column.label(text="Library Tools")
        # box_column.separator()
        box_column.operator("cat.show_missing_assets", icon="LIBRARY_DATA_BROKEN")
        box_column.operator("cat.find_asset_users", icon="LIBRARY_DATA_BROKEN")
        
        # box_column.separator()
        # box_column.label(text="Unreal Blender IO")
        # box_column.prop(parameters, "ubio_json_path", text="Path")
        # box_column.operator("cat.import_unreal_scene", icon="IMPORT")
        # box_column.operator("cat.export_unreal_scene_json", icon="EXPORT")
        # box_column.operator("cat.clean_ubio_tempfiles", icon="FILE_REFRESH")
        # box_column.separator()
        # box_column.label(text="UBIO Tools")
        # box_column.operator("cat.ubio_add_proxy_pivot", icon="EMPTY_ARROWS")
        # box_column.operator("cat.ubio_mirror_copy_actors", icon="MOD_MIRROR")
        # box_column.operator("cat.make_ue_actor_instance")
        
