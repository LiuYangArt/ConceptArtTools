import bpy
from mathutils import Vector

from .util import (
    CUSTOM_NAME,
    GROUP_MOD,
    INSTANCE_NAME,
    MG_SOCKET_GROUP,
    MG_SOCKET_OFFSET,
    PIVOT_NAME,
    WORLD_ORIGIN,
    check_is_mesh_group_instance,
    set_object_pivot_location,
)

READONLY_MODIFIER_ATTRIBUTES = {
    "bl_rna",
    "error_location",
    "error_rotation",
    "execution_time",
    "is_active",
    "name",
    "rna_type",
    "type",
}


# 复制 Modifier 可写参数。
# 参数:
#     source_modifier: 原 Object 上的 Modifier。
#     target_modifier: 新 Object 上同类型的 Modifier。
def copy_modifier_settings(source_modifier, target_modifier):
    for attribute_name in dir(source_modifier):
        if attribute_name.startswith("_") or attribute_name in READONLY_MODIFIER_ATTRIBUTES:
            continue
        try:
            setattr(target_modifier, attribute_name, getattr(source_modifier, attribute_name))
        except (AttributeError, TypeError):
            continue


# 查找 Mesh Group instance 上的自定义轴 Empty。
# 参数:
#     instance_object: 带 Mesh Group modifier 的实例 Object。
def find_custom_axis_object(instance_object):
    for child in instance_object.children:
        if child.type == "EMPTY" and child.get(CUSTOM_NAME) == PIVOT_NAME:
            return child
    return None


# 获取新 Collection 要挂载到的父 Collection。
# 参数:
#     instance_object: 当前要 apply 的 Mesh Group instance。
#     scene: 当前 Blender Scene。
def get_parent_collection(instance_object, scene):
    if instance_object.users_collection:
        return instance_object.users_collection[0]
    return scene.collection


# 把单个 Mesh Group instance 转成真实 Object。
# 参数:
#     instance_object: 当前要 apply 的 Mesh Group instance。
#     parent_collection: 新 Collection 要挂载到的父 Collection。
def apply_mesh_group_instance(instance_object, parent_collection):
    group_modifier = instance_object.modifiers.get(GROUP_MOD)
    if group_modifier is None:
        raise RuntimeError(f"Object {instance_object.name} does not have {GROUP_MOD}")

    source_group = group_modifier[MG_SOCKET_GROUP]
    if source_group is None:
        raise RuntimeError(f"Object {instance_object.name} has no source group")

    offset = Vector(group_modifier[MG_SOCKET_OFFSET])
    target_pivot_location = WORLD_ORIGIN - offset
    instance_location = instance_object.location.copy()
    new_collection = bpy.data.collections.new(instance_object.name)
    parent_collection.children.link(new_collection)

    applied_objects = []
    modifiers_to_copy = [
        modifier for modifier in instance_object.modifiers if modifier.name != GROUP_MOD
    ]
    axis_object = find_custom_axis_object(instance_object)
    axis_world_matrix = axis_object.matrix_world.copy() if axis_object else None

    for source_object in source_group.all_objects:
        new_object = source_object.copy()
        if source_object.data:
            new_object.data = source_object.data.copy()
        new_object.name = CUSTOM_NAME + source_object.name
        new_object.location = source_object.location
        new_object.rotation_euler = source_object.rotation_euler
        new_object.scale = source_object.scale
        new_collection.objects.link(new_object)

        if new_object.type == "MESH":
            set_object_pivot_location(new_object, target_pivot_location)
        new_object.location = instance_location

        for source_modifier in modifiers_to_copy:
            new_modifier = new_object.modifiers.new(source_modifier.name, source_modifier.type)
            copy_modifier_settings(source_modifier, new_modifier)

        applied_objects.append(new_object)

    if axis_object:
        for collection in list(axis_object.users_collection):
            collection.objects.unlink(axis_object)
        new_collection.objects.link(axis_object)
        axis_object.matrix_world = axis_world_matrix
        applied_objects.append(axis_object)

    bpy.data.objects.remove(instance_object)
    return applied_objects


class CAT_OT_apply_mesh_group(bpy.types.Operator):
    bl_idname = "cat.apply_mesh_group"
    bl_label = "Apply Mesh Group"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Turn Mesh Group instances into real mesh objects"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        selected_objects = list(context.selected_objects)
        applied_objects = []
        count = 0

        for obj in selected_objects:
            if not check_is_mesh_group_instance(obj):
                continue

            parent_collection = get_parent_collection(obj, context.scene)
            applied_objects.extend(apply_mesh_group_instance(obj, parent_collection))
            count += 1

        if count == 0:
            self.report({"INFO"}, "No Mesh Groups found to apply")
            return {"FINISHED"}

        bpy.ops.object.select_all(action="DESELECT")
        for obj in applied_objects:
            obj.select_set(True)

        self.report({"INFO"}, f"Applied {count} Mesh Group(s)")
        return {"FINISHED"}