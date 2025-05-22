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

def run_set_work_mode_op(self, context):
    """ 当ui参数改变时，运行对应的operator """
    bpy.ops.cat.set_work_mode('INVOKE_DEFAULT')

class UIParams(PropertyGroup):
    """UI参数"""
    work_mode: bpy.props.EnumProperty(
    name='Set View Mode',
    items=[
        ('DEFAULT', 'Blender Default',''),
        ('MODELING', 'Modeling Mode', ''),
        ('LIGHTING', 'Lighting Mode', ''),

    ],
    default='DEFAULT',
    #执行function， 运行对应的operator
    update=run_set_work_mode_op
    )

class InstancedCollectionToolPanel(bpy.types.Panel):
    bl_idname = "CAT_PT_tool_panel"
    bl_label = "ConceptArtTools"
    bl_category = "CAT" # Custom tab name
    bl_space_type = "VIEW_3D" # Space type where the panel will be displayed
    bl_region_type = "UI"
    bl_order = 0




    def draw(self, context):
        parameters = context.scene.cat_params
        layout = self.layout
        box = layout.box()
        box_column = box.column()
        box_column.label(text="Plasticity Group Instance")


        box_column.separator()
        # box_column.operator(
        #     "cat.instancing_group", icon="OUTLINER_OB_GROUP_INSTANCE"
        # ) 
        box_column.operator(
            "cat.make_mesh_group", icon="OUTLINER_OB_GROUP_INSTANCE"
        )


        
        box_column.operator(
            "cat.find_source_group", icon="VIEWZOOM"
        )
        # box_column.operator(
        #     "cat.mirror_instance", icon="MOD_MIRROR"
        # )
        # box_column.operator(
        #     "cat.array_instance", icon="MOD_ARRAY"
        # )
        # box_column.operator(
        #     "cat.remove_instance", icon="TRASH"
        # )

        box_column.operator(
            "cat.reset_pivot", icon="EMPTY_ARROWS"
        )
        box_column.operator(
            "cat.realize_meshgroup", icon="OBJECT_DATA"
        )
        box_column.operator(
            "cat.add_custom_axis", icon="ADD")
        box_column.operator(
            "cat.sync_materials_to_active", icon="MATERIAL")
        # box_column.operator(
        #     "cat.set_work_mode", icon="RESTRICT_SELECT_OFF")
        box_column.prop(parameters, "work_mode", text="Work Mode")

