import bpy
from mathutils import Vector
from .util import *


class MakeMeshGroupOperator(bpy.types.Operator):
    bl_idname = "cat.make_mesh_group"
    bl_label = "Make MeshGroup Instance"
    bl_description = (
        "Select one object and it will convert its' collection to a mesh-group instance"
    )
    bl_options = {"UNDO"}

    # UI Popup
    pivot: bpy.props.EnumProperty(
        name="Set pivot to",
        items=[
            ("CENTER", "Group Center", "Set pivot to origin center of objects", 1),
            ("LOWEST", "Group Bottom", "Set pivot to lowest center of objects", 2),
            (
                "SELECTED",
                "Selected",
                "Set pivot to center of selected elements. works in OBJECT and EDIT mode",
                3,
            ),
            ("CURSOR", "3D Cursor", "Set pivot to 3D cursor location", 4),
        ],
    )

    def execute(self, context):

        selected_objs = context.selected_objects
        current_mode = bpy.context.active_object.mode
        scene_coll = bpy.context.scene.collection
        source_groups = []
        instance_objs = []
        for obj in selected_objs:
            if obj.type == "MESH":
                if obj.users_collection[0] not in source_groups:
                    source_groups.append(obj.users_collection[0])

        if len(source_groups) > 0:
            # 导入用于生成Instance的Geometry Node
            import_node_group(preset_path, GROUP_NODE)

            for source_coll in source_groups:
                print(f"make instance for {source_coll.name} ")
                coll_objs = source_coll.all_objects

                if self.pivot == "CENTER":
                    offset = find_objs_bb_center(coll_objs)
                elif self.pivot == "LOWEST":
                    offset = find_objs_bb_lowest_center(coll_objs)
                elif self.pivot == "SELECTED":
                    offset = find_selected_element_center()
                elif self.pivot == "CURSOR":
                    cursor = bpy.context.scene.cursor
                    offset = cursor.location.copy()

                # current_mode = bpy.context.active_object.mode
                if current_mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")

                temp_mesh = bpy.data.meshes.new(TEMP_MESH)
                instance_obj = bpy.data.objects.new(
                    INST_PREFIX + source_coll.name, temp_mesh
                )
                scene_coll.objects.link(instance_obj)

                add_meshgroup_modifier(
                    instance_obj, target_group=source_coll, offset=offset
                )

                instance_obj.location = offset
                instance_obj[CUSTOM_NAME] = INSTANCE_NAME
                instance_objs.append(instance_obj)

                source_coll.hide_viewport = True
        # 复位
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.outliner.orphans_purge(do_local_ids=True)

        for obj in instance_objs:
            obj.select_set(True)

        return {"FINISHED"}

    def invoke(self, context, event):
        # #check if the selected object is valid
        selected_objs = context.selected_objects
        if len(selected_objs) == 0:
            self.report({"WARNING"}, "No selected objects")
            return {"CANCELLED"}

        obj = selected_objs[0]
        if obj.users_collection[0].name == "Scene Collection":
            self.report({"WARNING"}, "Selected object is not in a collection")
            return {"CANCELLED"}
        is_meshgroup = False
        try:
            if obj[CUSTOM_NAME] == INSTANCE_NAME or obj[CUSTOM_NAME] == PIVOT_NAME:
                is_meshgroup = True
        except:
            obj.type == "MESH"

        if is_meshgroup is True:
            self.report({"WARNING"}, "Selected object is already a INSTANCE")
            return {"CANCELLED"}

        # show dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class RealizeMeshGroupOperator(bpy.types.Operator):
    bl_idname = "cat.realize_meshgroup"
    bl_label = "RealizeMeshGroup"
    bl_options = {"UNDO"}
    bl_description = "Allow use with other modifiers, may lower performance if the group is too large"

    @classmethod
    def poll(cls, context):
        return all(
            [
                context.mode == "OBJECT",
                len(context.selected_objects),
            ]
        )

    def execute(self, context):
        selected_objs = context.selected_objects
        is_meshgroup = False
        count = 0
        for obj in selected_objs:
            if obj.type == "MESH":
                is_meshgroup = check_is_meshgroup_inst(obj)
                if is_meshgroup is True:
                    realize_meshgroup_modifier(obj, realize=True)
                    count += 1

        if is_meshgroup is False:
            self.report({"WARNING"}, "Selected object does not have any Instance")
            return {"CANCELLED"}

        else:
            self.report({"INFO"}, f"Realized {count} MeshGroup(s)")

        return {"FINISHED"}


class ResetPivotOperator(bpy.types.Operator):
    bl_idname = "cat.reset_pivot"
    bl_label = "Set Pivot Location"
    bl_description = "Change Pivot Location of Selected MeshGroup Instance"
    bl_options = {"UNDO"}

    # UI Popup
    pivot: bpy.props.EnumProperty(
        name="Set pivot to",
        items=[
            ("CENTER", "Group Center", "Set pivot to origin center of objects", 1),
            ("LOWEST", "Group Bottom", "Set pivot to lowest center of objects", 2),
            ("CURSOR", "3D Cursor", "Set pivot to 3D cursor location", 3),
        ],
    )

    @classmethod
    def poll(cls, context):
        return all(
            [
                context.mode == "OBJECT",
                len(context.selected_objects),
            ]
        )

    def execute(self, context):
        print("Set Pivot Location")
        selected_objs = context.selected_objects

        obj = selected_objs[0]
        obj_loc_raw = obj.location.copy()

        source_coll = obj.modifiers[GROUP_MOD][MG_SOCKET_GROUP]
        source_objs = source_coll.all_objects
        offset_raw = obj.modifiers[GROUP_MOD][MG_SOCKET_OFFSET]
        offset_raw = Vector((offset_raw[0], offset_raw[1], offset_raw[2]))
        offset_raw = offset_raw.copy()
        cursor = bpy.context.scene.cursor
        cursor_loc_view = cursor.location.copy()
        cursor_loc_target = cursor_loc_view - obj_loc_raw - offset_raw
        cursor.location = cursor_loc_target

        offset_new = cursor.location.copy()

        if self.pivot == "CENTER":
            offset_new = find_objs_bb_center(source_objs)
        elif self.pivot == "LOWEST":
            offset_new = find_objs_bb_lowest_center(source_objs)
        elif self.pivot == "CURSOR":
            offset_new = cursor.location.copy()

        add_meshgroup_modifier(obj, target_group=source_coll, offset=offset_new)
        obj_loc_new = obj.location + offset_raw + offset_new
        obj.location = obj_loc_new

        # 复位
        cursor.location = cursor_loc_view

        return {"FINISHED"}

    def invoke(self, context, event):
        selected_objs = context.selected_objects
        has_meshgroup_inst = False
        for obj in selected_objs:
            has_meshgroup_inst = check_is_meshgroup_inst(obj)
        if has_meshgroup_inst is False:
            self.report({"WARNING"}, "Selected objects does not have any Instance")
            return {"CANCELLED"}

        # show dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class FindSourceGroupOperator(bpy.types.Operator):
    bl_idname = "cat.find_source_group"
    bl_label = "Find Source Group"
    bl_description = "Find Source Group"

    @classmethod
    def poll(cls, context):
        return all(
            [
                context.mode == "OBJECT",
                len(context.selected_objects),
            ]
        )

    def execute(self, context):

        selected_objs = context.selected_objects
        if len(selected_objs) == 0:
            self.report({"WARNING"}, "No selected objects")
            return {"CANCELLED"}

        obj = selected_objs[0]
        is_meshgroup = check_is_meshgroup_inst(obj)

        if is_meshgroup is False:
            self.report({"WARNING"}, "Selected object is not a Instance")
            return {"CANCELLED"}
        elif is_meshgroup is True:
            # get the source collection
            source_coll = obj.modifiers[GROUP_MOD][MG_SOCKET_GROUP]
            source_coll.hide_viewport = False

            # select the source collection
            bpy.ops.object.select_all(action="DESELECT")
            coll_objs = source_coll.all_objects
            for obj in coll_objs:
                obj.select_set(True)

            bpy.ops.view3d.view_selected()

        return {"FINISHED"}


class AddCustomAxisOperator(bpy.types.Operator):
    bl_idname = "cat.add_custom_axis"
    bl_label = "Add Custom Axis Object"
    bl_description = (
        "Add a Custom Axis Object to the Instance for easier mirror modifier control"
    )
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return all(
            [
                context.mode == "OBJECT",
                len(context.selected_objects),
            ]
        )

    def execute(self, context):
        selected_objs = context.selected_objects
        if len(selected_objs) == 0:
            self.report({"WARNING"}, "No selected objects")
            return {"CANCELLED"}
        obj = selected_objs[0]
        is_meshgroup = check_is_meshgroup_inst(obj)
        has_axis = False
        if is_meshgroup is False:
            self.report({"WARNING"}, "Selected object is not a Instance")
            return {"CANCELLED"}
        for child in obj.children:
            if child.type == "EMPTY":
                if child[CUSTOM_NAME] == PIVOT_NAME:
                    has_axis = True
                    break
        if has_axis is True:
            bpy.ops.object.select_all(action="DESELECT")
            child.select_set(True)
            self.report({"INFO"}, "Object already has a Custom Axis")
            return {"CANCELLED"}

        axis_name = "Axis_" + obj.name
        axis_obj = bpy.data.objects.new(name=axis_name, object_data=None)
        # rename_alt(origin_object, origin_name, num=2)
        axis_obj[CUSTOM_NAME] = PIVOT_NAME
        axis_obj.empty_display_type = "ARROWS"
        axis_obj.empty_display_size = 0.4
        axis_obj.show_name = True

        obj.users_collection[0].objects.link(axis_obj)
        axis_obj.parent = obj
        bpy.ops.object.select_all(action="DESELECT")
        axis_obj.select_set(True)

        for mod in obj.modifiers:
            if mod.name == GROUP_MOD:
                mod[MG_SOCKET_REALIZE] = True
            if mod.type == "MIRROR":
                mod.mirror_object = axis_obj

        return {"FINISHED"}


# TODO: show/hide plasticity collection
