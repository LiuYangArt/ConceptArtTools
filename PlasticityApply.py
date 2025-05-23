import bpy

from .util import *

import sys
import io
from contextlib import redirect_stdout
import functools
from mathutils import Vector
#  全局存储控制台捕获对象
console_capture = None
stdout_orig = None
post_refacet_data = None  # 存储后续操作所需数据

class ConsoleCapture(io.StringIO):
    def __init__(self, filename):
        super().__init__()
        self.target_filename = filename
        self.completed = False

    def write(self, text):
        super().write(text)
        # 检查完成消息
        if f"Refaceting {self.target_filename} to version" in text:
            self.completed = True

def run_post_refacet_operations(context, target_filename, operator):
    """在 wm.refacet 完成后运行的自定义操作"""
    global post_refacet_data
    if not post_refacet_data:
        print("无后续操作数据")
        return
    
    bpy.ops.object.select_all(action='DESELECT')
    count = post_refacet_data["count"]
    refacted_objs = post_refacet_data["refacted_objs"]
    for data in post_refacet_data["source_group_visibility"]:
        hide_viewport= data["hide_viewport"]
        hide_select= data["hide_select"]


    for data in post_refacet_data["mesh_groups"]:
        obj = data["obj"]
        group_mod = data["group_mod"]
        obj_loc_inst = data["obj_loc_inst"]
        obj_loc_target = data["obj_loc_target"]
        cursor=context.scene.cursor
        cursor.location=obj_loc_target
        # # 后续操作（原 is_meshgroup 块）
        source_group = group_mod[MG_SOCKET_GROUP]
        source_objs = source_group.all_objects

        new_coll_name = obj.name
        new_coll = bpy.data.collections.new(new_coll_name)
        obj.users_collection[0].children.link(new_coll)
        for source_obj in source_objs:
            # 复制对象
            new_obj = source_obj.copy()
            new_obj.data = source_obj.data.copy()
            new_obj.name = CUSTOM_NAME + source_obj.name
            new_obj.location = source_obj.location
            new_obj.rotation_euler = source_obj.rotation_euler
            new_obj.scale = source_obj.scale
            new_coll.objects.link(new_obj)
            set_object_pivot_location(new_obj, obj_loc_target)
            new_obj.location = obj_loc_inst
            new_obj.select_set(True)
        bpy.data.objects.remove(obj)

        source_group.hide_viewport = hide_viewport
        # source_group.visibilty_set=hide_eye
        source_group.hide_select = hide_select


    # 清理
    post_refacet_data = None
    operator.report({'INFO'}, f"Apply {count} Mesh Group Finished, Refacet Finished")

def check_refacet_result(context, operator):
    print("check_refacet_result")
    global console_capture, stdout_orig, post_refacet_data
    # 检查捕获对象和上下文有效性
    if console_capture is None or stdout_orig is None:
        return None  # 停止定时器

    if not hasattr(context, 'scene') or context.scene is None:
        sys.stdout = stdout_orig  # 恢复 stdout
        console_capture = None
        post_refacet_data = None
        operator.report({'WARNING'}, "上下文失效，wm.refacet 检测中止")
        return None

    # 调试：记录捕获的输出
    captured_text = console_capture.getvalue()
    print(f"捕获输出: {captured_text[:100]}...")  # 截断以避免过长

    # 检查是否捕获到完成消息
    if console_capture.completed:
        target_filename = console_capture.target_filename  # 保存文件名
        
        sys.stdout = stdout_orig  # 恢复 stdout
        console_capture = None
        run_post_refacet_operations(context, target_filename, operator)  # 运行后续操作
        return None  # 停止定时器

    # 超时处理
    if not hasattr(check_refacet_result, "timer_count"):
        check_refacet_result.timer_count = 0
    check_refacet_result.timer_count += 1
    if check_refacet_result.timer_count > 300:  # 30 秒超时 (0.1s * 300)
        sys.stdout = stdout_orig  # 恢复 stdout
        console_capture = None
        post_refacet_data = None
        operator.report({'WARNING'}, f"Apply {post_refacet_data['count'] if post_refacet_data else 0} Mesh Group Finished, wm.refacet 超时，未检测到完成输出")
        return None

    return 0.1  # 每 0.1 秒检查一次

class ApplyMeshGroupOperator(bpy.types.Operator):
    bl_idname = "cat.apply_meshgroup"
    bl_label = "Apply Mesh Group"
    bl_options = {'UNDO'}
    bl_description = "Turn MeshGroup to Meshes"
    @classmethod
    def poll(cls, context):
        return all([
            context.mode == 'OBJECT',
            len(context.selected_objects),
        ])
    def execute(self, context):
        global console_capture, stdout_orig, post_refacet_data
        selected_objs = context.selected_objects
        count = 0
        plasticity_bridge = False
        refacet_objs = []
        mesh_groups = []  # 存储 MeshGroup 数据
        source_group_visibility = []
        # 推入撤销堆栈
        bpy.ops.ed.undo_push(message="Apply Mesh Group")

        for obj in selected_objs:
            is_meshgroup = False
            if obj.get(CUSTOM_NAME) == INSTANCE_NAME:  # 检查 CAT 实例
                group_mod = obj.modifiers.get(GROUP_MOD)
                if group_mod:
                    count += 1
                    is_meshgroup = True
                    obj_loc_inst = obj.location.copy()
                    offset_raw = group_mod[MG_SOCKET_OFFSET]
                    offset_raw = Vector((offset_raw[0], offset_raw[1], offset_raw[2]))
                    obj_loc_target = WORLD_ORIGIN - offset_raw

                    source_group = group_mod[MG_SOCKET_GROUP]
                    source_group_visibility.append({
                        "hide_viewport": source_group.hide_viewport,
                        "hide_select": source_group.hide_select,
                    })
                    source_group.hide_viewport = False
                    source_group.hide_select = False

                    source_objs = source_group.all_objects
                    bpy.ops.object.select_all(action='DESELECT')

                    # 收集需要 refacet 的对象
                    for source_obj in source_objs:
                        source_obj.select_set(True)
                        if source_obj not in refacet_objs:
                            refacet_objs.append(source_obj)

                    # 存储 MeshGroup 数据
                    mesh_groups.append({
                        "obj": obj,
                        "group_mod": group_mod,
                        "obj_loc_inst": obj_loc_inst,
                        "obj_loc_target": obj_loc_target
                    })

        # 检查是否需要 refacet
        if refacet_objs:
            try:
                # 设置为 NGON 模式并调用 refacet
                bpy.context.scene.prop_plasticity_facet_tri_or_ngon = 'NGON'
                bpy.ops.mesh.auto_mark_edges()

                # 获取目标文件名（单一文件名）
                target_filename = None
                for obj in refacet_objs:
                    if "plasticity_filename" in obj.keys():
                        target_filename = obj["plasticity_filename"]
                        break
                if not target_filename:
                    self.report({'ERROR'}, "未找到 plasticity_filename")
                    return {'CANCELLED'}

                # 检查 poll 条件
                if not bpy.ops.wm.refacet.poll():
                    self.report({'ERROR'}, "无法运行 wm.refacet：未满足条件（未连接 plasticity_client 或未选中带有 plasticity_id 的对象）")
                    return {'CANCELLED'}

                # 设置控制台捕获
                console_capture = ConsoleCapture(target_filename)
                stdout_orig = sys.stdout
                sys.stdout = console_capture
                self.report({'INFO'}, f"目标文件名: {target_filename}")

                # 调用 wm.refacet
                result = bpy.ops.wm.refacet()
                if result != {'FINISHED'}:
                    sys.stdout = stdout_orig
                    console_capture = None
                    self.report({'ERROR'}, "wm.refacet 执行失败")
                    return {'CANCELLED'}

                # 存储后续操作数据
                post_refacet_data = {
                    "count": count,
                    "refacted_objs": refacet_objs,
                    "mesh_groups": mesh_groups,
                    "source_group_visibility" : source_group_visibility
                }
                plasticity_bridge = True

                # 注册定时器
                bpy.app.timers.register(functools.partial(check_refacet_result, context, self))
                return {'RUNNING_MODAL'}  # 保持 Operator 运行直到定时器完成

            except Exception as e:
                sys.stdout = stdout_orig if stdout_orig else sys.__stdout__
                console_capture = None
                print(f"plasticity bridge not connected, skip refacet: {e}")

        # 若无需 refacet，直接执行后续操作
        if not plasticity_bridge and mesh_groups:
            run_post_refacet_operations(context, None, self)
            self.report({'INFO'}, f"Apply {count} Mesh Group Finished, Plasticity Bridge not connected, Refacet Skipped")
            return {'FINISHED'}

        # 若无 MeshGroup，直接返回
        self.report({'INFO'}, f"No Mesh Groups found to apply")
        return {'FINISHED'}