import bpy
class InstancedCollectionToolPanel(bpy.types.Panel):
    bl_idname = "CAT_PT_tool_panel"
    bl_label = "Plasticity Group Instance"
    bl_category = "CAT" # Custom tab name
    bl_space_type = "VIEW_3D" # Space type where the panel will be displayed
    bl_region_type = "UI"
    bl_order = 0



    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box_column = box.column()
        box_column.label(text="Instanced Collection")


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
        
        

