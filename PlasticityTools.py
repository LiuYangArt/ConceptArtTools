import bpy
from mathutils import Vector,Matrix
from .util import *

#Constants



class MakeMeshGroupOperator(bpy.types.Operator):
    bl_idname = "cat.make_mesh_group"
    bl_label = "MakeMeshGroup"
    bl_options = {'UNDO'}

    #UI Popup
    pivot: bpy.props.EnumProperty(
        name='Set pivot to',
        items=[
            ('CENTER', 'Group Center', 
            'Set pivot to origin center of objects', 1),
            ('LOWEST', 'Group Bottom', 
            'Set pivot to lowest center of objects', 2),

            ('SELECTED', 'Selected object', 
            'Set pivot to selected object center', 3),
            ('CURSOR', '3D Cursor',
            'Set pivot to 3D cursor location', 4),
        ]
    )


    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])

    def execute(self, context):


        
        selected_objs = context.selected_objects
        scene_coll = bpy.context.scene.collection
        source_coll=selected_objs[0].users_collection[0]
        coll_objs=source_coll.all_objects


        if self.pivot == 'CENTER':
            offset = find_objs_bb_center(coll_objs)
        elif self.pivot == 'LOWEST':
            offset = find_objs_bb_lowest_center(coll_objs)
        elif self.pivot == 'SELECTED':
            offset = find_objs_bb_center(selected_objs)
        elif self.pivot == 'CURSOR':
            cursor = bpy.context.scene.cursor
            offset = cursor.location.copy()


        

        import_node_group(preset_path, GROUP_NODE)




        for mesh in bpy.data.meshes:         #search if temp mesh already exist
            if mesh.name == TEMP_MESH:
                temp_mesh=mesh
                break
        else:
            #create a new mesh
            temp_mesh=bpy.data.meshes.new(TEMP_MESH)
        instance_obj=bpy.data.objects.new(source_coll.name, temp_mesh)
        scene_coll.objects.link(instance_obj)

   

        add_meshgroup_modifier(instance_obj,target_group=source_coll,offset=offset)


        instance_obj.location = offset
        instance_obj[CUSTOM_NAME]=INSTANCE_NAME



        #复位

        bpy.ops.object.select_all(action='DESELECT')
        instance_obj.select_set(True)

        return {"FINISHED"}
    
    def invoke(self, context, event):
        # #check if the selected object is valid
        selected_objs = context.selected_objects
        if len(selected_objs) == 0:
            self.report({'WARNING'}, "No selected objects")
            return {"CANCELLED"}
        
        obj=selected_objs[0]
        is_meshgroup=False
        try:
            if obj[CUSTOM_NAME]==INSTANCE_NAME or obj[CUSTOM_NAME]==PIVOT_NAME:
                is_meshgroup=True
        except:
            obj.type=='MESH'

        if is_meshgroup is True:
            self.report({'WARNING'}, "Selected object is already a INSTANCE")
            return {"CANCELLED"}
        #show dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

class RealizeMeshGroupOperator(bpy.types.Operator):
    bl_idname = "cat.realize_meshgroup"
    bl_label = "RealizeMeshGroup"
    bl_options = {'UNDO'}
    bl_description = "Realize Instance, you need this ON to use modifiers"
    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        selected_objs = context.selected_objects
        is_meshgroup=False
        count=0
        for obj in selected_objs:
            if obj.type == 'MESH':
                is_meshgroup=check_is_meshgroup_inst(obj)
                if is_meshgroup is True:
                    realize_meshgroup_modifier(obj,realize=True)
                    count+=1

        if is_meshgroup is False:
            self.report({'WARNING'}, "Selected object does not have any Instance")
            return {"CANCELLED"}
        
        else:
            self.report({'INFO'}, f"Realized {count} MeshGroup(s)")

        return {"FINISHED"}



class ResetPivotOperator(bpy.types.Operator):
    bl_idname = "cat.reset_pivot"
    bl_label = "Set Pivot Location"
    bl_options = {'UNDO'}

    # UI Popup
    pivot: bpy.props.EnumProperty(
        name='Set pivot to',
        items=[
            ('CENTER', 'Group Center', 
            'Set pivot to origin center of objects', 1),
            ('LOWEST', 'Group Bottom', 
            'Set pivot to lowest center of objects', 2),
            ('CURSOR', '3D Cursor',
            'Set pivot to 3D cursor location', 3),
        ]
    )
    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        print("Set Pivot Location")
        selected_objs = context.selected_objects

        obj=selected_objs[0]
        obj_loc_raw=obj.location.copy()
  
        source_coll=obj.modifiers[GROUP_MOD]["Socket_2"]
        source_objs=source_coll.all_objects
        offset_raw=obj.modifiers[GROUP_MOD]["Socket_7"]
        offset_raw=Vector((offset_raw[0],offset_raw[1],offset_raw[2]))
        offset_raw=offset_raw.copy()
        cursor = bpy.context.scene.cursor
        cursor_loc_view=cursor.location.copy()
        cursor_loc_target=cursor_loc_view-obj_loc_raw-offset_raw
        cursor.location=cursor_loc_target

        offset_new=cursor.location.copy()

        if self.pivot == 'CENTER':
            offset_new = find_objs_bb_center(source_objs)
        elif self.pivot == 'LOWEST':
            offset_new = find_objs_bb_lowest_center(source_objs)
        elif self.pivot == 'CURSOR':
            offset_new = cursor.location.copy()


        add_meshgroup_modifier(obj,target_group=source_coll,offset=offset_new)
        obj_loc_new=obj.location+offset_raw+offset_new
        obj.location=obj_loc_new



        
        #复位
        cursor.location=cursor_loc_view

        return {"FINISHED"}
    
    def invoke(self, context, event):
        selected_objs = context.selected_objects
        has_meshgroup_inst=False
        for obj in selected_objs:
            has_meshgroup_inst=check_is_meshgroup_inst(obj)
        if has_meshgroup_inst is False:
            self.report({'WARNING'}, "Selected objects does not have any Instance")
            return {"CANCELLED"}

        #show dialog
        wm = context.window_manager
        return wm.invoke_props_dialog(self)





class FindSourceGroupOperator(bpy.types.Operator):
    bl_idname = "cat.find_source_group"
    bl_label = "Find Source Group"

    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])

    def execute(self, context):

        selected_objs = context.selected_objects
        if len(selected_objs) == 0:
            self.report({'WARNING'}, "No selected objects")
            return {"CANCELLED"}
        
        obj=selected_objs[0]
        is_meshgroup=check_is_meshgroup_inst(obj)

        if is_meshgroup is False:
            self.report({'WARNING'}, "Selected object is not a Instance")
            return {"CANCELLED"}
        elif is_meshgroup is True:
            #get the source collection
            source_coll=obj.modifiers[GROUP_MOD]["Socket_2"]

            #select the source collection
            bpy.ops.object.select_all(action='DESELECT')

            coll_objs=source_coll.all_objects
            print(coll_objs)
            for obj in coll_objs:
                obj.select_set(True)
            bpy.ops.view3d.view_selected()


        return {"FINISHED"}



# class MirrorInstanceOperator(bpy.types.Operator):
#     bl_idname = "cat.mirror_instance"
#     bl_label = "Mirror Instance"
#     bl_options = {'UNDO'}

#     axis: bpy.props.EnumProperty(
#         name='Axis',
#         items=[
#             ('X', 'X', 
#             'Set pivot to origin center of objects', 1),
#             ('Y', 'Y', 
#             'Set pivot to lowest center of objects', 2),
#             ('Z', 'Z', 
#             'Set pivot to selected object center', 3),
#         ]
#     )

#     @classmethod
#     def poll(cls, context):
#         return all([
#             context.mode == 'OBJECT',
#             len(context.selected_objects),
#         ])


#     def execute(self, context):
#         axis=0
#         if self.axis == 'X':
#             axis=0
#         elif self.axis == 'Y':
#             axis=1
#         elif self.axis == 'Z':
#             axis=2

#         selected_objs = context.selected_objects

#         for obj in selected_objs:
#             has_meshgroup_inst=check_is_meshgroup_inst(obj)
#             if has_meshgroup_inst is True:
#                 modifier=obj.modifiers[GROUP_MOD]
#                 modifier["Socket_3"] = True
#                 add_mirror_modifier(obj,axis=axis)

#         return {"FINISHED"}

#     def invoke(self, context, event):
#         selected_objs = context.selected_objects
#         has_mesh_group_inst=False
#         for obj in selected_objs:
#             has_meshgroup_inst=check_is_meshgroup_inst(obj)
#         if has_meshgroup_inst is False:
#             self.report({'WARNING'}, "Selected objects does not have any Instance")
#             return {"CANCELLED"}
#         wm = context.window_manager
#         return wm.invoke_props_dialog(self)


# class ArrayInstanceOperator(bpy.types.Operator):
#     bl_idname = "cat.array_instance"
#     bl_label = "Array Instance"
#     bl_options = {'UNDO'}

#     @classmethod
#     def poll(cls, context):
#         return all([
#             context.mode == 'OBJECT',
#             len(context.selected_objects),
#         ])


#     def execute(self, context):

#         selected_objs = context.selected_objects
#         has_meshgroup_inst=False
#         for obj in selected_objs:
#             has_meshgroup_inst=check_is_meshgroup_inst(obj)
#             if has_meshgroup_inst is True:
#                 modifier=obj.modifiers[GROUP_MOD]
#                 modifier["Socket_3"] = True
#                 add_array_modifier(obj)
#         if has_meshgroup_inst is False:
#             self.report({'WARNING'}, "Selected objects does not have any Instance")
#             return {"CANCELLED"}
#         return {"FINISHED"}


# class RemoveInstanceOperator(bpy.types.Operator):
#     bl_idname = "cat.remove_instance"
#     bl_label = "Remove Instance"
#     bl_options = {'UNDO'}

#     @classmethod
#     def poll(cls, context):
#         return all([
#             context.mode == 'OBJECT',
#             len(context.selected_objects),
#         ])

#     def execute(self, context):
#         selected_objs = context.selected_objects
#         has_meshgroup_inst=False
#         for obj in selected_objs:
#             has_meshgroup_inst=check_is_meshgroup_inst(obj)
#             is_instance_coll=False
#             if obj.instance_collection:
#                 is_instance_coll=True
#             if has_meshgroup_inst is True:
#                 bpy.data.objects.remove(obj.parent)
#                 bpy.data.objects.remove(obj)
#             elif is_instance_coll is True:
#                 bpy.data.objects.remove(obj)
#         if has_meshgroup_inst is False and is_instance_coll is False:
#             self.report({'WARNING'}, "Selected objects does not have any Instance")
#             return {"CANCELLED"}
#         return {"FINISHED"}

