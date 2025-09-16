import bpy
import random

# CONST
COLLECTION_ENV_COLOR = "COLOR_03"


# Sort collections alphabetically
def sort_children(collection):
    if not collection.children:
        return
    # Get children names and sort them
    sorted_names = sorted([c.name for c in collection.children])

    # Re-link children in sorted order
    for name in sorted_names:
        child_coll = bpy.data.collections[name]
        # Unlink and re-link to move to the end of the list
        collection.children.unlink(child_coll)
        collection.children.link(child_coll)
        sort_children(child_coll)


# Helper function to get or create a collection
def get_or_create_collection(name, parent_collection, color_tag="NONE"):
    if name in parent_collection.children:
        coll = parent_collection.children[name]
    else:
        coll = bpy.data.collections.new(name)
        parent_collection.children.link(coll)
    coll.color_tag = color_tag
    return coll


class ORGANIZE_OT_lights_and_cameras(bpy.types.Operator):
    """Organize all lights and cameras into dedicated collections"""

    bl_idname = "cat.organize_lights_and_cameras"
    bl_label = "Organize Lights and Cameras"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        has_lights = any(obj.type == "LIGHT" for obj in scene.objects)
        has_cameras = any(obj.type == "CAMERA" for obj in scene.objects)

        if not has_lights and not has_cameras:
            self.report({"INFO"}, "No lights or cameras found in the current scene.")
            return {"CANCELLED"}

        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        master_collection = scene.collection

        has_lights = any(obj.type == "LIGHT" for obj in scene.objects)
        has_cameras = any(obj.type == "CAMERA" for obj in scene.objects)

        # Create collections
        env_coll = get_or_create_collection(
            "_Env", master_collection, COLLECTION_ENV_COLOR
        )
        if has_lights:
            lights_coll = get_or_create_collection(
                "Lights", env_coll, COLLECTION_ENV_COLOR
            )
        if has_cameras:
            cameras_coll = get_or_create_collection(
                "Cameras", env_coll, COLLECTION_ENV_COLOR
            )

        if env_coll:
            for child in env_coll.children:
                # set color tag
                child.color_tag = COLLECTION_ENV_COLOR

        # Get all collections the objects are currently in
        all_collections = bpy.data.collections

        # Move objects
        for obj in scene.objects:
            # Unlink from all other collections except the target one
            def unlink_from_all(target_coll):
                for coll in obj.users_collection:
                    if coll != target_coll:
                        coll.objects.unlink(obj)

            if obj.type == "LIGHT":
                unlink_from_all(lights_coll)
                if obj.name not in lights_coll.objects:
                    lights_coll.objects.link(obj)
            elif obj.type == "CAMERA":
                unlink_from_all(cameras_coll)
                if obj.name not in cameras_coll.objects:
                    cameras_coll.objects.link(obj)

        # Remove empty collections that are not the master collection or the ones we just created
        collections_to_remove = []
        # Use a set for faster lookups
        protected_collections = {master_collection}
        if "env_coll" in locals():
            protected_collections.add(env_coll)
        if "lights_coll" in locals():
            protected_collections.add(lights_coll)
        if "cameras_coll" in locals():
            protected_collections.add(cameras_coll)

        for coll in bpy.data.collections:
            if (
                coll not in protected_collections
                and not coll.objects
                and not coll.children
            ):
                collections_to_remove.append(coll)

        for coll in collections_to_remove:
            # The collection might have been removed already if it was a child of another removed collection
            if coll.name in bpy.data.collections:
                bpy.data.collections.remove(coll)

        # Sort root collections
        sort_children(master_collection)
        # Sort collections inside '_Env'
        if "env_coll" in locals() and env_coll.name in master_collection.children:
            sort_children(env_coll)

        # Report completion

        self.report({"INFO"}, "Lights and cameras have been organized.")
        return {"FINISHED"}


class ORGANIZE_OT_colorize_collection_objects(bpy.types.Operator):
    """Colorize objects based on their collection"""

    bl_idname = "cat.colorize_collection_objects"
    bl_label = "Colorize Objects by Collection"
    bl_options = {"REGISTER", "UNDO"}

    #TODO: 1. 对子Collection也需要同样进行处理。2.不再考虑选中的objects，而是直接处理当前scene下所有的collection  3. 修改Viewport模式，切换到 bpy.context.space_data.shading.light = 'STUDIO' bpy.context.space_data.shading.color_type = 'OBJECT'


    def invoke(self, context, event):
        # 1. Check if there are any selected objects.
        if not context.selected_objects:
            self.report(
                {"WARNING"}, "No objects selected. Please select objects to colorize."
            )
            return {"CANCELLED"}

        # Check if selected objects are in any collection. This is almost always true.
        # A more practical check is just ensuring objects are selected.
        has_collection = any(obj.users_collection for obj in context.selected_objects)
        if not has_collection:
            self.report({"WARNING"}, "Selected objects are not in any collection.")
            return {"CANCELLED"}

        return self.execute(context)

    def execute(self, context):
        # 2. Get the collections that the selected objects belong to.
        selected_objects = context.selected_objects
        collections_to_colorize = set()
        for obj in selected_objects:
            for coll in obj.users_collection:
                collections_to_colorize.add(coll)

        if not collections_to_colorize:
            self.report(
                {"INFO"}, "Selected objects are not in any user-created collections."
            )
            return {"CANCELLED"}

        # 3. For each collection, assign a different object color to its objects.
        for coll in collections_to_colorize:
            # Generate a random color for each collection
            color = (random.random(), random.random(), random.random(), 1.0)
            for obj in coll.objects:
                obj.color = color

        self.report(
            {"INFO"}, f"Colorized objects in {len(collections_to_colorize)} collection(s)."
        )
        return {"FINISHED"}

