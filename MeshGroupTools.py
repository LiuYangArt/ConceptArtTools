import bpy
import bmesh
from mathutils import Vector

from .util import (
    CUSTOM_NAME,
    GROUP_MOD,
    GROUP_NODE,
    GROUP_ROOT_COLL,
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


# 判断 parent Collection 是否已经直接包含 child Collection。
# 参数:
#     parent_collection: Blender Collection，待检查的父 Collection。
#     child_collection: Blender Collection，待检查的子 Collection。
def collection_has_child(parent_collection, child_collection):
    return any(child == child_collection for child in parent_collection.children)


# 查找 target Collection 在 root Collection 树中的直接父 Collection。
# 参数:
#     root_collection: Blender Collection，作为查找入口的根 Collection。
#     target_collection: Blender Collection，需要查找父级的 Collection。
def find_collection_parents(root_collection, target_collection):
    parents = []
    for child_collection in root_collection.children:
        if child_collection == target_collection:
            parents.append(root_collection)
            continue
        parents.extend(find_collection_parents(child_collection, target_collection))
    return parents


# 判断 Collection 是否存在于指定 Scene 的 Collection 树中。
# 参数:
#     scene: Blender Scene，待检查的 Scene。
#     target_collection: Blender Collection，需要查找的 Collection。
def collection_is_in_scene(scene, target_collection):
    return target_collection == scene.collection or bool(
        find_collection_parents(scene.collection, target_collection)
    )


# 获取或创建 Mesh Group source 专用 Scene。
# 参数: 无。
def get_or_create_source_scene():
    source_scene = bpy.data.scenes.get(GROUP_ROOT_COLL)
    if source_scene is None:
        source_scene = bpy.data.scenes.new(GROUP_ROOT_COLL)
    return source_scene


# 确保 source Collection 已挂到 Mesh Group source 专用 Scene。
# 参数:
#     source_collection: Blender Collection，Mesh Group modifier 引用的 source Collection。
def ensure_source_collection_in_source_scene(source_collection):
    source_scene = get_or_create_source_scene()
    if not collection_has_child(source_scene.collection, source_collection):
        source_scene.collection.children.link(source_collection)
    return source_scene


# 把 source Collection 移到专用 Scene，并从当前 Scene 的 Collection 树移除。
# 参数:
#     source_collection: Blender Collection，Mesh Group modifier 引用的 source Collection。
#     current_scene: Blender Scene，执行 make mesh group 时所在的原 Scene。
def move_source_collection_to_scene(source_collection, current_scene):
    if source_collection == current_scene.collection:
        return False

    source_scene = ensure_source_collection_in_source_scene(source_collection)

    if current_scene == source_scene:
        return True

    for parent_collection in find_collection_parents(
        current_scene.collection,
        source_collection,
    ):
        parent_collection.children.unlink(source_collection)

    return True


# 收集 Collection 及其所有子 Collection。
# 参数:
#     collection: Blender Collection，递归收集入口。
def get_collection_tree(collection):
    collections = [collection]
    for child_collection in collection.children:
        collections.extend(get_collection_tree(child_collection))
    return collections


# 收集当前文件中仍被 Mesh Group instance 引用的 source Collection。
# 参数: 无。
def get_referenced_source_collections():
    source_collections = set()
    for obj in bpy.data.objects:
        if not check_is_mesh_group_instance(obj):
            continue
        group_modifier = obj.modifiers.get(GROUP_MOD)
        if group_modifier and group_modifier[MG_SOCKET_GROUP]:
            source_collections.add(group_modifier[MG_SOCKET_GROUP])
    return source_collections


# 判断 source Collection 树是否仍被任意 Mesh Group instance 引用。
# 参数:
#     collection: Blender Collection，需要检查的 source Collection 根节点。
#     referenced_collections: set，当前文件中仍被引用的 source Collection 集合。
def source_collection_tree_is_referenced(collection, referenced_collections):
    collection_tree = set(get_collection_tree(collection))
    return bool(collection_tree.intersection(referenced_collections))


# 删除 source Collection 树中的 Object 与 Collection datablock。
# 参数:
#     collection: Blender Collection，需要删除的 source Collection 根节点。
def remove_source_collection_tree(collection):
    collection_tree = get_collection_tree(collection)
    source_objects = set(collection.all_objects)

    for obj in source_objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    for child_collection in reversed(collection_tree):
        if child_collection.name in bpy.data.collections:
            bpy.data.collections.remove(child_collection, do_unlink=True)

    return len(source_objects)


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
    move_source_to_scene: bpy.props.BoolProperty(
        name="Move Source to Scene",
        description="Move source collections to the Mesh Group source scene",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pivot")
        layout.prop(self, "realize")
        layout.prop(self, "move_source_to_scene")

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
        if self.move_source_to_scene:
            for source_collection in source_groups:
                move_source_collection_to_scene(source_collection, context.scene)

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
        if not collection_is_in_scene(context.scene, source_collection):
            source_scene = ensure_source_collection_in_source_scene(source_collection)
            if context.window:
                context.window.scene = source_scene
        source_collection.hide_viewport = False

        bpy.ops.object.select_all(action="DESELECT")
        for source_object in source_collection.all_objects:
            source_object.select_set(True)

        bpy.ops.view3d.view_selected()
        return {"FINISHED"}


class CAT_OT_cleanup_source_groups(bpy.types.Operator):
    bl_idname = "cat.cleanup_source_groups"
    bl_label = "Cleanup Source Groups"
    bl_description = "Delete Mesh Group source collections that are not referenced by any instance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        source_scene = bpy.data.scenes.get(GROUP_ROOT_COLL)
        if source_scene is None:
            self.report({"INFO"}, "No source scene found")
            return {"FINISHED"}

        referenced_collections = get_referenced_source_collections()
        removed_collections = 0
        removed_objects = 0
        for source_collection in list(source_scene.collection.children):
            if source_collection_tree_is_referenced(
                source_collection,
                referenced_collections,
            ):
                continue

            removed_objects += remove_source_collection_tree(source_collection)
            removed_collections += 1

        bpy.ops.outliner.orphans_purge(do_local_ids=True)
        self.report(
            {"INFO"},
            f"Removed {removed_collections} source group(s), {removed_objects} object(s)",
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)

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