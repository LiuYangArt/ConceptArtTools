import bpy
import re
import uuid
from pathlib import Path

from bpy_extras import asset_utils

from .util import (
    GROUP_MOD,
    MG_SOCKET_GROUP,
    check_is_mesh_group_instance,
)

ASSET_STORAGE_SCENE = "_CAT_AssetInstances"
ASSET_CATALOG_PATH = "Concept Art Tools/Instances"
ASSET_CATALOG_SIMPLE_NAME = "Instances"
ASSET_CATALOG_UUID = str(
    uuid.uuid5(uuid.NAMESPACE_URL, "ConceptArtTools.MeshGroupInstances")
)
ASSET_SOURCE_COLLECTION_PROP = "CAT_asset_source_collection"


# 移除 Blender 自动添加的 .001 这类数字后缀。
# 参数:
#     name: 需要清理的 Blender datablock 名称。
def strip_blender_numeric_suffix(name):
    return re.sub(r"\.\d{3}$", "", name)


# 生成 Mesh Group asset 的显示名称。
# 参数:
#     source_collection: Mesh Group instance 引用的 source Collection。
def get_asset_object_name(source_collection):
    return "Asset_" + strip_blender_numeric_suffix(source_collection.name)


# 设置 Object 名称，必要时只替换指定的旧 Object 名称占用。
# 参数:
#     obj: 需要命名的 Object。
#     name: 目标名称。
#     replace_object: 允许被 Blender 自动改名让位的旧 Object。
def rename_object_cleanly(obj, name, replace_object=None):
    conflict_object = bpy.data.objects.get(name)
    if conflict_object is not None and conflict_object != obj and conflict_object == replace_object:
        obj.rename(name, mode="ALWAYS")
        return

    obj.name = name


# 获取 Mesh Group instance 引用的 source Collection。
# 参数:
#     instance_object: 带 CAT_MeshGroup Geometry Nodes modifier 的 instance Object。
def get_instance_source_collection(instance_object):
    group_modifier = instance_object.modifiers.get(GROUP_MOD)
    if group_modifier is None:
        raise RuntimeError(f"Object {instance_object.name} does not have {GROUP_MOD}")

    source_collection = group_modifier[MG_SOCKET_GROUP]
    if source_collection is None:
        raise RuntimeError(f"Object {instance_object.name} has no source Collection")

    return source_collection


# 获取或创建保存 asset instance 的专用 Scene。
# 参数: 无。
def get_or_create_asset_storage_scene():
    storage_scene = bpy.data.scenes.get(ASSET_STORAGE_SCENE)
    if storage_scene is None:
        storage_scene = bpy.data.scenes.new(ASSET_STORAGE_SCENE)
    return storage_scene


# 判断 Object 是否已经在指定 Scene 中。
# 参数:
#     obj: 需要检查的 Blender Object。
#     scene: 作为查询范围的 Blender Scene。
def object_is_in_scene(obj, scene):
    return any(scene_object == obj for scene_object in scene.objects)


# 解析 Asset Catalog Definition File 中的 catalog 行。
# 参数:
#     line: CDF 文件中的单行文本。
def parse_catalog_line(line):
    stripped_line = line.strip()
    if not stripped_line or stripped_line.startswith("#") or stripped_line.startswith("VERSION"):
        return None

    parts = stripped_line.split(":", 2)
    if len(parts) != 3:
        return None

    return parts[0], parts[1], parts[2]


# 获取当前 Asset Browser 选中的 Catalog UUID。
# 参数:
#     context: 当前 Blender operator context。
def get_active_asset_browser_catalog_id(context):
    if context.screen is None:
        return None

    for area in context.screen.areas:
        space_data = area.spaces.active
        if not asset_utils.SpaceAssetInfo.is_asset_browser(space_data):
            continue
        catalog_id = space_data.params.catalog_id
        if catalog_id != "00000000-0000-0000-0000-000000000000":
            return catalog_id
    return None


# 确保当前 blend 文件目录中存在本工具使用的 asset catalog。
# 参数:
#     context: 当前 Blender operator context，用于未保存文件时复用当前 Asset Browser Catalog。
def ensure_instance_asset_catalog(context):
    if not bpy.data.filepath:
        return get_active_asset_browser_catalog_id(context)

    catalog_file = Path(bpy.data.filepath).parent / "blender_assets.cats.txt"
    catalog_line = (
        f"{ASSET_CATALOG_UUID}:{ASSET_CATALOG_PATH}:{ASSET_CATALOG_SIMPLE_NAME}"
    )

    if not catalog_file.exists():
        catalog_file.write_text(
            "# This is an Asset Catalog Definition file for Blender.\n"
            "# Empty lines and lines starting with # are ignored.\n"
            "VERSION 1\n\n"
            f"{catalog_line}\n",
            encoding="utf-8",
        )
        return ASSET_CATALOG_UUID

    lines = catalog_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        parsed_line = parse_catalog_line(line)
        if parsed_line is None:
            continue

        catalog_id, catalog_path, _simple_name = parsed_line
        if catalog_path == ASSET_CATALOG_PATH:
            return catalog_id
        if catalog_id == ASSET_CATALOG_UUID:
            return catalog_id

    lines.append(catalog_line)
    catalog_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ASSET_CATALOG_UUID


# 查找已经 mark asset 且引用同一个 source Collection 的 Mesh Group instance。
# 参数:
#     source_collection: Mesh Group instance 引用的 source Collection。
def find_asset_instance_by_source_collection(source_collection):
    for obj in bpy.data.objects:
        if obj.asset_data is None or not check_is_mesh_group_instance(obj):
            continue
        if get_instance_source_collection(obj) == source_collection:
            return obj
    return None


# 复制 Mesh Group instance 到 asset storage scene。
# 参数:
#     instance_object: 当前选中的 Mesh Group instance Object。
#     storage_scene: 用于安全保存 asset Object 的专用 Scene。
#     replace_object: 允许被新 asset 名称替换的旧 Object。
def copy_instance_to_asset_storage(instance_object, storage_scene, replace_object=None):
    source_collection = get_instance_source_collection(instance_object)
    asset_object = instance_object.copy()
    if instance_object.data:
        asset_object.data = instance_object.data.copy()

    asset_name = get_asset_object_name(source_collection)
    rename_object_cleanly(asset_object, asset_name, replace_object)
    asset_object[ASSET_SOURCE_COLLECTION_PROP] = source_collection.name_full
    storage_scene.collection.objects.link(asset_object)
    return asset_object


# 把 Object 标记为当前工具的 asset，并归入统一 catalog。
# 参数:
#     asset_object: 需要显示在 Asset Browser 中的 Object datablock。
#     catalog_id: 要写入 asset metadata 的 Catalog UUID。
def mark_object_as_instance_asset(asset_object, catalog_id):
    if asset_object.asset_data is None:
        asset_object.asset_mark()
    if catalog_id:
        asset_object.asset_data.catalog_id = catalog_id
    asset_object.asset_data.description = "Concept Art Tools Mesh Group Instance"
    asset_object.asset_generate_preview()


# 刷新当前 Screen 中打开的 Asset Browser 区域。
# 参数:
#     context: 当前 Blender operator context。
def refresh_asset_browser_areas(context):
    if context.screen is None:
        return

    for area in context.screen.areas:
        space_data = area.spaces.active
        if not asset_utils.SpaceAssetInfo.is_asset_browser(space_data):
            area.tag_redraw()
            continue

        window_region = next(
            (region for region in area.regions if region.type == "WINDOW"),
            None,
        )
        if window_region is None:
            area.tag_redraw()
            continue

        with context.temp_override(
            area=area,
            region=window_region,
            space_data=space_data,
        ):
            if bpy.ops.asset.library_refresh.poll():
                bpy.ops.asset.library_refresh()
        area.tag_redraw()


class CAT_OT_add_selected_instances_to_asset_browser(bpy.types.Operator):
    bl_idname = "cat.add_selected_instances_to_asset_browser"
    bl_label = "Add Instances to Asset Browser"
    bl_description = "Copy selected Mesh Group instances to asset storage and mark them as assets"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        storage_scene = get_or_create_asset_storage_scene()
        catalog_id = ensure_instance_asset_catalog(context)
        source_collections = set()
        added_count = 0
        skipped_count = 0
        replaced_count = 0

        for obj in context.selected_objects:
            if not check_is_mesh_group_instance(obj):
                continue

            source_collection = get_instance_source_collection(obj)
            if source_collection in source_collections:
                skipped_count += 1
                continue
            source_collections.add(source_collection)

            existing_asset = find_asset_instance_by_source_collection(source_collection)
            if existing_asset and object_is_in_scene(existing_asset, storage_scene):
                rename_object_cleanly(existing_asset, get_asset_object_name(source_collection))
                mark_object_as_instance_asset(existing_asset, catalog_id)
                skipped_count += 1
                continue

            if existing_asset:
                existing_asset.asset_clear()

            asset_object = copy_instance_to_asset_storage(
                obj,
                storage_scene,
                replace_object=existing_asset,
            )
            mark_object_as_instance_asset(asset_object, catalog_id)
            added_count += 1

            if existing_asset:
                replaced_count += 1

        if added_count == 0 and skipped_count == 0:
            self.report({"WARNING"}, "Selected objects do not have any Mesh Group instance")
            return {"CANCELLED"}

        refresh_asset_browser_areas(context)

        message = f"Added {added_count}, skipped {skipped_count}"
        if replaced_count:
            message += f", replaced {replaced_count} unsafe asset(s)"
        if not catalog_id:
            message += "; save the file or select a catalog first"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        if not any(check_is_mesh_group_instance(obj) for obj in context.selected_objects):
            self.report({"WARNING"}, "Selected objects do not have any Mesh Group instance")
            return {"CANCELLED"}

        return self.execute(context)