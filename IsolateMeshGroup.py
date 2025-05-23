import bpy
from .util import *
EDIT_SCENE_PREFIX = "_CAT_temp:"
LIGHT_COLLECTION_NAME =  "_CAT_Lights"
def get_all_lights():
    return [obj for obj in bpy.data.objects if obj.type == "LIGHT"]



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
            #list all collections in this scene
            groups=[]
            for c in scene.collection.children:
                groups.append(c.name)
            bpy.data.scenes.remove(scene)
            bpy.ops.outliner.orphans_purge(do_local_ids=True)
            for c in bpy.data.collections:
                if c.name in groups:
                    c.hide_viewport=True
            # for g in groups:
            #     for c in bpy.data.collections:1
            #     if c.name==g:
            #         # bpy.data.collections.remove(c)
            #         print("collection removed")
            #         print("source group found")
            return True
        else: #not in edit mode
            return False
    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        # prefs = context.preferences.addons[package_name].preferences
        selected_objects = bpy.context.selected_objects
        active_obj = bpy.context.active_object
        source_group = None
        if len(selected_objects) == 0:
            quit_edit=self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
            return {"FINISHED"}

        # print(f"Active object: {bpy.context.active_object}")

        # Check if the active object is a collection instance
        if active_obj is None:
            print("No active object")
            quit_edit=self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
                return {"FINISHED"}
        if active_obj.get(CUSTOM_NAME) == INSTANCE_NAME:  # 检查 CAT 实例
            group_mod = active_obj.modifiers.get(GROUP_MOD)
            if group_mod:
                source_group = group_mod[MG_SOCKET_GROUP]
                # source_objs = source_group.all_objects
            

        if not source_group:
            print("Active item is not a MeshGroup Instance")
            quit_edit=self.quit_edit_scene()
            if quit_edit:
                self.report({"INFO"}, "Already in edit scene mode, Quit Edit")
                return {"FINISHED"}


            self.report({"WARNING"}, "Active item is not a MeshGroup Instance")
            return {"CANCELLED"}
        

        print(f"Editing Group: {source_group.name}")
        all_lights=get_all_lights()
        # get current world, get current world node tree
        scene_world = bpy.context.scene.world
        if scene_world:
            scene_world_tree = scene_world.node_tree

        #temp_scene_name
        scene_name = f"{EDIT_SCENE_PREFIX}{source_group.name}"
        bpy.ops.scene.new(type="EMPTY")
        edit_scene = bpy.context.scene
        edit_scene.name = scene_name
        bpy.context.window.scene = edit_scene
        edit_scene.collection.children.link(source_group)
        if len(all_lights) > 0:
            # print("Lights found")
            light_collection = bpy.data.collections.new(LIGHT_COLLECTION_NAME)
            edit_scene.collection.children.link(light_collection)
            light_collection.hide_select = True
            for light in all_lights:
                #new collection : _Lights
                light_collection.objects.link(light)
        #scene background
        if scene_world_tree.nodes: #use base scene background
            edit_scene.world = scene_world
        elif not scene_world_tree: # create a new world when there is no world
            edit_scene = bpy.data.worlds.new(bpy.context.scene.name)
            # edit_scene.world = world
            edit_scene.world.use_nodes = True
            tree = edit_scene.world.node_tree
            tree.nodes["Background"].inputs["Color"].default_value = (.3, .3, .3, 1)
            
        # Select the collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[source_group.name]
        source_group.hide_viewport = False
        source_objs = source_group.all_objects
        for obj in source_objs:
            obj.select_set(True)

            
        bpy.ops.view3d.view_selected()

        return {"FINISHED"}