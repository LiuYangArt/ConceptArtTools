import bpy
import random

# CONST
COLLECTION_ENV_COLOR = "COLOR_03"


# Sort collections alphabetically
def sort_children(collection,case_sensitive=False):
    """Sort children of a collection alphabetically"""
    if collection.children is None:
            return

    children = sorted(
        collection.children,
        key=lambda c: c.name if case_sensitive else c.name.lower(),
    )

    for child in children:
        collection.children.unlink(child)
        collection.children.link(child)
        sort_children(child)



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
        # # Sort collections inside '_Env'
        # if "env_coll" in locals() and env_coll.name in master_collection.children:
        #     sort_children(env_coll)

        # Report completion

        self.report({"INFO"}, "Lights and cameras have been organized.")
        return {"FINISHED"}


class ORGANIZE_OT_colorize_collection_objects(bpy.types.Operator):
    """Colorize objects based on their collection hierarchy"""

    bl_idname = "cat.colorize_collection_objects"
    bl_label = "Colorize Objects by Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Set viewport shading to show object colors
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.light = "STUDIO"
                        space.shading.color_type = "OBJECT"
                        break

        # Recursive function to colorize objects in a collection and its children
        def colorize_recursively(collection):
            # Generate a random color for the current collection
            color = (random.random(), random.random(), random.random(), 1.0)
            # Color objects in the current collection
            for obj in collection.objects:
                obj.color = color
            # Recurse for child collections
            for child in collection.children:
                colorize_recursively(child)

        # Process all top-level collections in the scene
        master_collection = context.scene.collection
        if not master_collection.children:
            self.report({"INFO"}, "No collections found to colorize.")
            return {"CANCELLED"}

        for coll in master_collection.children:
            colorize_recursively(coll)

        self.report(
            {"INFO"},
            "Colorized objects by collection.",
        )
        return {"FINISHED"}
