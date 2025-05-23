import bpy
from .util import *

EDIT_SCENE_PREFIX = "_CAT_temp:"
LIGHT_COLLECTION_NAME = "_CAT_Lights"


def get_all_lights():
    return [obj for obj in bpy.data.objects if obj.type == "LIGHT"]


# new_location=obj.location+offset


class EditCollection(bpy.types.Operator):
    """Edit the Collection referenced by this Collection Instance in a new Scene"""

    bl_idname = "cat.isolate_group"
    bl_label = "Isolate Group"
    bl_description = "Toggle Edit Source Group, good for material authorin"
    bl_options = {"REGISTER", "UNDO"}

    def quit_edit_scene(self):
        """remove temp edit collection-instance scene and clean up data"""
        scene = bpy.context.scene
        if scene.name.startswith(EDIT_SCENE_PREFIX):
            # list all collections in this scene
            groups = []
            for coll in scene.collection.children:
                groups.append(coll.name)
            bpy.data.scenes.remove(scene)
            bpy.ops.outliner.orphans_purge(do_local_ids=True)
            for coll in bpy.data.collections:
                if coll.name in groups:
                    for obj in coll.all_objects:
                        obj.location = WORLD_ORIGIN
                    coll.hide_viewport = True

            return True
        else:  # not in edit mode
            return False

    def execute(self, context):
        # prefs = context.preferences.addons[package_name].preferences
        selected_objects = bpy.context.selected_objects
        active_obj = bpy.context.active_object
        source_group = None
        if len(selected_objects) == 0:
            quit_edit = self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
            return {"FINISHED"}

        # 检查ActiveObject是否MeshGroup Instance
        if active_obj is None:
            print("No active object")
            quit_edit = self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
                return {"FINISHED"}
        if active_obj.get(CUSTOM_NAME) == INSTANCE_NAME:  # 检查是否有 CAT 属性标记
            group_mod = active_obj.modifiers.get(GROUP_MOD)
            if group_mod:  # 获取MeshGroup Instance的参数
                source_group = group_mod[MG_SOCKET_GROUP]
                inst_offset = group_mod[MG_SOCKET_OFFSET]
                inst_offset = Vector((inst_offset[0], inst_offset[1], inst_offset[2]))
                inst_location = active_obj.location.copy()
                # source_objs = source_group.all_objects

        if not source_group:
            print("Active item is not a MeshGroup Instance")
            quit_edit = self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
                return {"FINISHED"}

            self.report({"WARNING"}, "Active item is not a MeshGroup Instance")
            return {"CANCELLED"}

        # print(f"Editing Group: {source_group.name}")
        self.report({"INFO"}, f"Editing Group: {source_group.name}")

        all_lights = get_all_lights()
        # get current world, get current world node tree
        scene_world = bpy.context.scene.world
        if scene_world:
            scene_world_tree = scene_world.node_tree

        # temp_scene_name
        scene_name = f"{EDIT_SCENE_PREFIX}{source_group.name}"
        bpy.ops.scene.new(type="EMPTY")
        edit_scene = bpy.context.scene
        edit_scene.name = scene_name
        bpy.context.window.scene = edit_scene
        edit_scene.collection.children.link(source_group)

        # 把主场景中的灯光复制到编辑场景中，确保显示效果一致
        if len(all_lights) > 0:
            light_collection = bpy.data.collections.new(LIGHT_COLLECTION_NAME)
            edit_scene.collection.children.link(light_collection)
            light_collection.hide_select = True
            for light in all_lights:
                light_collection.objects.link(light)
        # 复制主场景的Wolrd shader， 保证环境光一致
        if scene_world_tree.nodes:  # use base scene background
            edit_scene.world = scene_world
        elif not scene_world_tree:  # create a new world when there is no world
            edit_scene = bpy.data.worlds.new(bpy.context.scene.name)
            # edit_scene.world = world
            edit_scene.world.use_nodes = True
            tree = edit_scene.world.node_tree
            tree.nodes["Background"].inputs["Color"].default_value = (0.3, 0.3, 0.3, 1)

        # Select the collection
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection.children[source_group.name]
        )
        source_group.hide_viewport = False
        source_objs = source_group.all_objects
        for obj in source_objs:
            # obj.location
            obj.location = inst_location - inst_offset
            obj.select_set(True)

        bpy.ops.view3d.view_selected()

        return {"FINISHED"}
