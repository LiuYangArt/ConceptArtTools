# # buggy when setting instance pivot/ recreate instance, do not use
# class InstancingGroupOperator(bpy.types.Operator):
#     bl_idname = "cat.instancing_group"
#     bl_label = "Instancing Group"
#     bl_options = {'UNDO'}

#     #UI Popup


#     pivot: bpy.props.EnumProperty(
#         name='Set pivot to',
#         items=[
#             ('CENTER', 'Origin center', 
#             'Set pivot to origin center of objects', 1),
#             ('LOWEST', 'Lowest center', 
#             'Set pivot to lowest center of objects', 2),

#             ('SELECTED', 'Selected object', 
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
#         # scene = bpy.data.scenes.new(self.collection_name)

#         selected_objs = context.selected_objects
#         source_coll=selected_objs[0].users_collection[0]
#         coll_objs=source_coll.all_objects
#         cursor = bpy.context.scene.cursor
#         cursor_current_transform = cursor.matrix.copy()
#         bpy.ops.view3d.snap_cursor_to_center()



#         if self.pivot == 'CENTER':
#             offset = find_objs_bb_center(coll_objs)
#         elif self.pivot == 'LOWEST':
#             offset = find_objs_bb_lowest_center(coll_objs)
#         elif self.pivot == 'SELECTED':
#             offset = find_objs_bb_center(selected_objs)

        


#         if source_coll is None:
#             self.report({'WARNING'}, "Object has no collection")
#             return {"CANCELLED"}
#         else:

#             bpy.ops.object.collection_instance_add(
#                 align="WORLD",
#                 collection=source_coll.name,
#                 location=Vector((0,0,0)))

        
#         #move group instance to scene collection
#         instance=context.active_object
#         scene_coll = bpy.context.scene.collection
#         if instance.users_collection[0] != scene_coll:
#             instance.users_collection[0].objects.unlink(instance)
#             scene_coll.objects.link(instance)
#         instance[CUSTOM_NAME]=INSTANCE_NAME
#         bpy.ops.object.select_all(action='DESELECT')
#         instance.select_set(True)
#         cursor.location=offset
#         bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
#         cursor.matrix = cursor_current_transform
            

        


#         return {'FINISHED'}