import bpy
import bmesh
from mathutils import Vector

from .util import (
    CUSTOM_NAME,
    GROUP_MOD,
    GROUP_NODE,
    INSTANCE_NAME,
    INST_PREFIX,
    MG_SOCKET_GROUP,
    MG_SOCKET_OFFSET,
    MG_SOCKET_REALIZE,
    PIVOT_NAME,
    PRESET_PATH,
    TEMP_MESH,
    add_mesh_group_modifier,
    check_is_mesh_group_instance,
    find_objs_bb_center,
    find_objs_bb_lowest_center,
    find_selected_element_center,
    import_node_group,
    realize_mesh_group_modifier,
)


class CAT_OT_make_mesh_group(bpy.types.Operator):
    bl_idname = "cat.make_mesh_group"
    bl_label = "Make Mesh Group Instance"
    bl_description = (
        "Convert selected object collections to Mesh Group instances. In Edit Mode, "
        "selected vertices define the pivot."
    )
    bl_options = {"REGISTER", "UNDO"}

    pivot: bpy.props.EnumProperty(
        name="Set pivot to",
        items=[
            ("CENTER", "Group Center", "Set pivot to origin center of objects", 1),
            ("LOWEST", "Group Bottom", "Set pivot to lowest center of objects", 2),
            (
                "SELECTED",
                "Selected",
                "Set pivot to center of selected elements in Object or Edit Mode",
                3,
            ),
            ("CURSOR", "3D Cursor", "Set pivot to 3D cursor location", 4),
        ],
        default="CENTER",
    )
    realize: bpy.props.BoolProperty(
        name="Realize",
        description="Realize Mesh Group instances for use with modifiers",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pivot")
        layout.prop(self, "realize")

    def execute(self, context):
        selected_objects = context.selected_objects
        active_object = context.active_object
        current_mode = active_object.mode if active_object else "OBJECT"
        scene_collection = context.scene.collection
        source_groups = []
        instance_objects = []

        for obj in selected_objects:
            if obj.type == "MESH" and obj.users_collection:
                source_collection = obj.users_collection[0]
                if source_collection not in source_groups:
                    source_groups.append(source_collection)

        if not source_groups:
            self.report({"WARNING"}, "Selected objects are not in a source collection")
            return {"CANCELLED"}

        for source_collection in source_groups:
            collection_objects = source_collection.all_objects

            if self.pivot == "CENTER":
                offset = find_objs_bb_center(collection_objects)
            elif self.pivot == "LOWEST":
                offset = find_objs_bb_lowest_center(collection_objects)
            elif self.pivot == "SELECTED":
                offset = find_selected_element_center() or find_objs_bb_center(collection_objects)
            elif self.pivot == "CURSOR":
                offset = context.scene.cursor.location.copy()
            else:
                offset = Vector((0, 0, 0))

            if current_mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            import_node_group(PRESET_PATH, GROUP_NODE)
            temp_mesh = bpy.data.meshes.new(TEMP_MESH)
            instance_object = bpy.data.objects.new(
                INST_PREFIX + source_collection.name,
                temp_mesh,
            )
            scene_collection.objects.link(instance_object)

            geometry_nodes_modifier = add_mesh_group_modifier(
                instance_object,
                target_group=source_collection,
                offset=offset,
            )
            geometry_nodes_modifier[MG_SOCKET_REALIZE] = self.realize

            instance_object.location = offset
            instance_object[CUSTOM_NAME] = INSTANCE_NAME
            instance_objects.append(instance_object)

        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.outliner.orphans_purge(do_local_ids=True)
        for source_collection in source_groups:
            source_collection.hide_viewport = True
            source_collection.hide_render = True
        for obj in instance_objects:
            obj.select_set(True)

        return {"FINISHED"}

    def invoke(self, context, event):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({"WARNING"}, "No selected objects")
            return {"CANCELLED"}

        first_object = selected_objects[0]
        if not first_object.users_collection:
            self.report({"WARNING"}, "Selected object is not in a collection")
            return {"CANCELLED"}
        if first_object.get(CUSTOM_NAME) in {INSTANCE_NAME, PIVOT_NAME}:
            self.report({"WARNING"}, "Selected object is already an instance")
            return {"CANCELLED"}

        edit_mesh_objects = [
            obj for obj in selected_objects if obj.type == "MESH" and obj.mode == "EDIT"
        ]
        for obj in edit_mesh_objects:
            if any(vertex.select for vertex in bmesh.from_edit_mesh(obj.data).verts):
                self.pivot = "SELECTED"
                break

        return self.execute(context)


class CAT_OT_realize_mesh_group(bpy.types.Operator):
    bl_idname = "cat.realize_mesh_group"
    bl_label = "Realize Mesh Group"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Allow use with other modifiers; may lower performance on large groups"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type == "MESH" and check_is_mesh_group_instance(obj):
                realize_mesh_group_modifier(obj, realize=True)
                count += 1

        if count == 0:
            self.report({"WARNING"}, "Selected object does not have any instance")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Realized {count} Mesh Group(s)")
        return {"FINISHED"}


class CAT_OT_reset_pivot(bpy.types.Operator):
    bl_idname = "cat.reset_pivot"
    bl_label = "Set Pivot Location"
    bl_description = "Change pivot location of selected Mesh Group instance"
    bl_options = {"REGISTER", "UNDO"}

    pivot: bpy.props.EnumProperty(
        name="Set pivot to",
        items=[
            ("CENTER", "Group Center", "Set pivot to origin center of objects", 1),
            ("LOWEST", "Group Bottom", "Set pivot to lowest center of objects", 2),
            ("CURSOR", "3D Cursor", "Set pivot to 3D cursor location", 3),
        ],
        default="CENTER",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def draw(self, context):
        self.layout.prop(self, "pivot")

    def execute(self, context):
        selected_objects = context.selected_objects
        obj = selected_objects[0]
        object_location_before = obj.location.copy()

        source_collection = obj.modifiers[GROUP_MOD][MG_SOCKET_GROUP]
        source_objects = source_collection.all_objects
        offset_before = Vector(obj.modifiers[GROUP_MOD][MG_SOCKET_OFFSET]).copy()
        cursor = context.scene.cursor
        cursor_location_before = cursor.location.copy()
        cursor.location = cursor_location_before - object_location_before - offset_before

        if self.pivot == "CENTER":
            offset_after = find_objs_bb_center(source_objects)
        elif self.pivot == "LOWEST":
            offset_after = find_objs_bb_lowest_center(source_objects)
        elif self.pivot == "CURSOR":
            offset_after = cursor.location.copy()
        else:
            offset_after = Vector((0, 0, 0))

        add_mesh_group_modifier(obj, target_group=source_collection, offset=offset_after)
        obj.location = obj.location + offset_before + offset_after
        cursor.location = cursor_location_before

        return {"FINISHED"}

    def invoke(self, context, event):
        if not any(check_is_mesh_group_instance(obj) for obj in context.selected_objects):
            self.report({"WARNING"}, "Selected objects do not have any instance")
            return {"CANCELLED"}

        return self.execute(context)


class CAT_OT_find_source_group(bpy.types.Operator):
    bl_idname = "cat.find_source_group"
    bl_label = "Find Source Group"
    bl_description = "Find Source Group"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        obj = context.selected_objects[0]
        if not check_is_mesh_group_instance(obj):
            self.report({"WARNING"}, "Selected object is not an instance")
            return {"CANCELLED"}

        source_collection = obj.modifiers[GROUP_MOD][MG_SOCKET_GROUP]
        source_collection.hide_viewport = False

        bpy.ops.object.select_all(action="DESELECT")
        for source_object in source_collection.all_objects:
            source_object.select_set(True)

        bpy.ops.view3d.view_selected()
        return {"FINISHED"}


class CAT_OT_add_custom_axis(bpy.types.Operator):
    bl_idname = "cat.add_custom_axis"
    bl_label = "Add Custom Axis Object"
    bl_description = "Add a Custom Axis Object to the instance for easier Mirror modifier control"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        obj = context.selected_objects[0]
        if not check_is_mesh_group_instance(obj):
            self.report({"WARNING"}, "Selected object is not an instance")
            return {"CANCELLED"}

        for child in obj.children:
            if child.type == "EMPTY" and child.get(CUSTOM_NAME) == PIVOT_NAME:
                bpy.ops.object.select_all(action="DESELECT")
                child.select_set(True)
                self.report({"INFO"}, "Object already has a Custom Axis")
                return {"CANCELLED"}

        axis_object = bpy.data.objects.new(name="Axis_" + obj.name, object_data=None)
        axis_object[CUSTOM_NAME] = PIVOT_NAME
        axis_object.empty_display_type = "ARROWS"
        axis_object.empty_display_size = 0.4
        axis_object.show_name = True

        obj.users_collection[0].objects.link(axis_object)
        axis_object.parent = obj
        bpy.ops.object.select_all(action="DESELECT")
        axis_object.select_set(True)

        for modifier in obj.modifiers:
            if modifier.name == GROUP_MOD:
                modifier[MG_SOCKET_REALIZE] = True
            if modifier.type == "MIRROR":
                modifier.mirror_object = axis_object

        return {"FINISHED"}