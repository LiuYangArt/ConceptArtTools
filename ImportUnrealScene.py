import bpy
import os
import json
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import Vector, Euler
from math import radians

GUID = "ue_guid"
FNAME = "ue_fname"
ACTORTYPE = "ue_actortype"
ACTORCLASS = "ue_class"
UECOLL = "UnrealIO"
MAINLEVEL = "MainLevel"
COLL_ROOT = "Root"
COLL_MAIN = "Main"
COLL_LEVEL = "Level"
UECOLL_COLOR = "COLOR_06"
COLLINST_TYPES = ["Blueprint"]


def make_collection(collection_name: str, type:str="") -> bpy.types.Collection:
    """建立指定名称的Collection，并可选设置自定义属性"""
    if collection_name not in bpy.data.collections:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)
        coll[UECOLL] = type
    else:
        coll = bpy.data.collections[collection_name]
    
    return coll


def move_objs_to_collection(objs, collection_name: str) -> None:
    """将指定对象移动到指定集合中"""
    coll = make_collection(collection_name)
    for obj in objs:
        # 先从所有已链接的collection移除
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)


def get_name_from_ue_path(path: str) -> str:
    """从UE路径中提取名称"""
    # # 先取最后一个/后的部分
    # last_part = path.split('/')[-1]
    # # 再取最后一个.后的部分
    name = path.split(".")[-1]
    return name


class CAT_OT_ImportUnrealScene(bpy.types.Operator):
    bl_idname = "cat.import_unreal_scene"
    bl_label = "Import Unreal Scene"
    bl_description = "Import FBX and JSON exported from Unreal Engine"
    bl_options = {"UNDO"}

    def execute(self, context):
        params = context.scene.cat_params
        json_path = params.ueio_json_path

        # 检查json_path是否存在
        if not os.path.exists(json_path):
            self.report({"ERROR"}, f"找不到JSON文件: {json_path}")
            return {"CANCELLED"}
        print(json_path)
        # 解析JSON文件
        with open(json_path, "r") as f:
            scene_data = json.load(f)

        # 构建FBX文件路径
        fbx_path = os.path.splitext(json_path)[0] + ".fbx"

        # 检查FBX文件是否存在
        if not os.path.exists(fbx_path):
            self.report({"ERROR"}, f"找不到对应的FBX文件: {fbx_path}")
            return {"CANCELLED"}
        # 导入FBX，设置参数：导入custom normal，不导入动画
        # 记录导入前的对象集合

        # 从json获得 main_level 和 level_path 两个数据
        main_level = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)

        main_level_name = get_name_from_ue_path(main_level)
        if main_level == level_path:
            level_path_name = MAINLEVEL
        else:
            level_path_name=get_name_from_ue_path(level_path)
        

        # make collections
        ueio_coll = make_collection(UECOLL,type=COLL_ROOT)
        main_level_coll = make_collection(main_level_name,type=COLL_MAIN)
        level_path_coll = make_collection(level_path_name,type=COLL_LEVEL)

        ueio_coll.color_tag = UECOLL_COLOR


        # 设置从属关系: ueio_coll > main_level_coll > level_path_coll
        if main_level_coll.name not in [c.name for c in ueio_coll.children]:
            ueio_coll.children.link(main_level_coll)
        if level_path_coll.name not in [c.name for c in main_level_coll.children]:
            main_level_coll.children.link(level_path_coll)
        scene_coll = bpy.context.scene.collection
        for coll in [main_level_coll, level_path_coll]:
            if coll.name in [c.name for c in scene_coll.children]:
                scene_coll.children.unlink(bpy.data.collections[coll.name])

        existing_objs = set(bpy.data.objects)

        bpy.ops.import_scene.fbx(
            filepath=fbx_path,
            use_custom_normals=True,
            use_custom_props=False,
            use_image_search=False,
            use_anim=False,
            bake_space_transform=True,
        )

        # 导入后得到新对象
        ueio_objs = [obj for obj in bpy.data.objects if obj not in existing_objs]
        move_objs_to_collection(ueio_objs, level_path_coll.name)

        # 检查Blender单位设置
        if bpy.context.scene.unit_settings.length_unit != "CENTIMETERS":
            self.report({"WARNING"}, "Blender单位不是厘米，可能会导致比例不一致")
        vaild_actors = []
        # 处理每个actor
        level_instance_objs = []
        for obj in ueio_objs:
            if obj.type == "EMPTY" and "LevelInstanceEditorInstanceActor" in obj.name:
                level_instance_objs.append(obj)
        for actor in scene_data["actors"]:
            # print(f"处理 {actor['name']},type {actor['actor_type']}")
            obj = bpy.data.objects.get(actor["name"])
            if obj:
                # 设置自定义属性
                obj[GUID] = str(actor["fguid"])
                obj[FNAME] = actor["fname"]
                obj[ACTORTYPE] = actor["actor_type"]
                obj[ACTORCLASS] = actor["class"]

                is_coll_inst = False
                is_light = False
                # 如果 obj[ACTORTYPE] 属于 COLLINST_TYPES中的任意一种, convert_to_actor_instance(obj)
                if obj[ACTORTYPE] in COLLINST_TYPES:
                    is_coll_inst = True
                elif obj[ACTORTYPE] == "LevelInstance":
                    for inst in level_instance_objs:
                        if obj.location == inst.location:
                            inst.parent = obj
                            inst.location = (0, 0, 0)
                            is_coll_inst = True
                elif "Light" in obj[ACTORTYPE]:
                    is_light = True
                else:
                    continue

                if is_coll_inst:
                    if obj in ueio_objs:
                        ueio_objs.remove(obj)
                    actor_obj = convert_to_actor_instance(obj)
                    vaild_actors.append(actor_obj)
                elif is_light:
                    vaild_actors.append(obj)
                    obj.hide_select = True
        for obj in ueio_objs:
            if obj.type == "EMPTY" and len(obj.children) == 0:
                obj.hide_viewport = True
                obj.hide_select = True

                # 应用变换
                # bpy.context.view_layer.objects.active = obj
                # obj.select_set(True)
                # bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
                # obj.select_set(False)

        self.report({"INFO"}, f"成功导入Unreal场景: {os.path.basename(json_path)}")
        return {"FINISHED"}


def get_all_children(obj):
    children = []
    for child in obj.children:
        children.append(child)
        children.extend(get_all_children(child))
    return children


def convert_to_actor_instance(actor_obj):
    """把ue fbx导入actor的empty集合转换成更适合在blender中使用的collection instance"""
    actor_name = actor_obj.name
    target_collection = actor_obj.users_collection[0]
    temp_scene = bpy.data.scenes.new(actor_name)
    # 检查是否存在 actor_type 属性
    actor_type = actor_obj.get(ACTORTYPE, None)
    actor_guid = actor_obj.get(GUID, None)
    actor_fname = actor_obj.get(FNAME, None)
    actor_class = actor_obj.get(ACTORCLASS, None)
    # actor object 判断
    if actor_obj.type == "EMPTY":
        if actor_obj.instance_collection is not None:
            return None
        if actor_type is None:
            return None
        target_location = actor_obj.location.copy()
        target_rotation = actor_obj.rotation_euler.copy()
        target_scale = actor_obj.scale.copy()
        target_objs = get_all_children(actor_obj)
    else:
        return None

    # 从原scene中移出，添加到临时scene的新collection中
    for target_obj in target_objs:
        for c in target_obj.users_collection:
            c.objects.unlink(target_obj)
        if target_obj.type == "EMPTY":
            # 修改empty的显示，size=0.01
            target_obj.empty_display_size = 0.01

    scene_coll = temp_scene.collection
    new_coll = bpy.data.collections.new(actor_name)
    scene_coll.children.link(new_coll)
    for o in target_objs:
        new_coll.objects.link(o)
        o.location = o.location

    # 删除原对象
    bpy.data.objects.remove(actor_obj)
    # 在场景中添加collection instance
    bpy.ops.object.collection_instance_add(
        collection=new_coll.name,
        location=target_location,
        rotation=target_rotation,
        scale=target_scale,
    )
    bpy.data.scenes.remove(temp_scene)
    # 写入自定义属性用于后续json导出
    new_actor_obj = bpy.data.objects[actor_name]
    new_actor_obj[GUID] = actor_guid
    new_actor_obj[FNAME] = actor_fname
    new_actor_obj[ACTORTYPE] = actor_type
    new_actor_obj[ACTORCLASS] = actor_class
    # 移动到原collection
    new_actor_obj.users_collection[0].objects.unlink(new_actor_obj)
    target_collection.objects.link(new_actor_obj)
    return new_actor_obj


class CAT_OT_ExportUnrealJSON(bpy.types.Operator):
    bl_idname = "cat.export_unreal_scene_json"
    bl_label = "Export Unreal Scene JSON"
    bl_description = "Export Unreal Scene JSON"
    bl_options = {"UNDO"}

    def execute(self, context):
        params = context.scene.cat_params
        json_path = params.ueio_json_path

        # 检查json文件是否存在
        if not os.path.exists(json_path):
            self.report({"ERROR"}, f"找不到JSON文件: {json_path}")
            return {"CANCELLED"}

        # 解析JSON文件
        with open(json_path, "r") as f:
            scene_data = json.load(f)

        # 找到UECOLL下的collection
        ueio_coll = bpy.data.collections.get(UECOLL)
        if not ueio_coll:
            self.report({"ERROR"}, f"找不到集合: {UECOLL}")
            return {"CANCELLED"}

        # 找到UECOLL的子collection（level_asset_coll），以及main_level
        level_asset_coll = None
        main_level_coll = None
        is_mainlevel = False
        sub_colls = get_all_children(ueio_coll)
        for coll in sub_colls:
            coll_type = coll.get(UECOLL, None)
            print(coll.name)
            print(coll_type)
            if coll_type == COLL_MAIN:
                main_level_coll = coll
            elif coll_type == COLL_LEVEL:
                level_asset_coll = coll
        if level_asset_coll.name == MAINLEVEL:
            is_mainlevel = True
            print(f"{main_level_coll.name} is mainlevel")

        # # 如果只有一个子collection，默认是level_asset_coll
        # if not level_asset_coll and ueio_coll.children:
        #     level_asset_coll = list(ueio_coll.children)[0]

        # if not level_asset_coll:
        #     self.report({"ERROR"}, "未找到Level Asset Collection")
        #     return {"CANCELLED"}

        # 获取json中的main_level和level_path
        main_level_path = scene_data.get("main_level", None)
        level_path = scene_data.get("level_path", None)
        main_level_name = get_name_from_ue_path(main_level_path)
        level_name = get_name_from_ue_path(level_path)
        is_match_json = False
        if main_level_coll.name==main_level_name:
            if is_mainlevel:
                is_match_json = True
            else:
                if level_asset_coll.name==level_name:
                    is_match_json = True
        if is_match_json==False:
            self.report({'WARNING'}, "Current scene does not match the UEIO JSON")
            return {"CANCELLED"}

        # 获取level_asset_coll下的所有对象
        level_actor_objs = [obj for obj in level_asset_coll.objects]

        # 遍历json中的actors，匹配Blender对象
        for actor in scene_data.get("actors", []):
            actor_name = actor.get("name")
            actor_type = actor.get("actor_type")
            actor_fname = actor.get("fname")
            actor_guid = str(actor.get("fguid"))

            # 在Blender对象中查找匹配
            for obj in level_actor_objs:
                if (
                    obj.name == actor_name
                    and str(obj.get(ACTORTYPE, "")) == actor_type
                    and str(obj.get(FNAME, "")) == actor_fname
                    and str(obj.get(GUID, "")) == actor_guid
                ):
                    # 匹配成功，更新json中的transform为Blender中的transform
                    print(f"匹配到对象：{obj.name}")
                    loc = obj.location * 100
                    rot = obj.rotation_euler
                    # Blender和UE坐标系：Y轴取反
                    # 角度转换
                    rot_deg = [((r * 180.0 / 3.141592653589793) % 360) for r in rot]
                    scale = obj.scale

                    # 写入到json的transform字段
                    actor["transform"] = {
                        "location": {
                            "x": loc.x,
                            "y": -loc.y,
                            "z": loc.z
                        },
                        "rotation": {
                            "x": rot_deg[0],
                            "y": -rot_deg[1],
                            "z": rot_deg[2]
                        },
                        "scale": {
                            "x": scale.x,
                            "y": scale.y,
                            "z": scale.z
                        }
                    }
                    print(f"transform: {actor['transform']}")

        # 保存修改后的json
        with open(json_path, "w") as f:
            json.dump(scene_data, f, indent=4)

        self.report({"INFO"}, "已同步Blender对象变换到JSON文件")
        return {"FINISHED"}


class CAT_OT_MakeUEActorInstance(bpy.types.Operator):
    """Collapses selected meshes into one collection and spawns its instance here."""  # NOQA

    bl_idname = "cat.make_ue_actor_instance"
    bl_label = "这是一个测试用的operator"
    bl_options = {"UNDO"}

    def execute(self, context):
        selected_objs = context.selected_objects
        for obj in selected_objs:
            convert_to_actor_instance(obj)

        # clean up temp datas
        bpy.ops.outliner.orphans_purge(do_local_ids=True)

        return {"FINISHED"}
