import bpy
import os

# --- 辅助函数：查找特定节点组的材质用户 (基于之前的脚本) ---
def find_materials_using_nodegroup_for_report(target_ng_datablock):
    materials_found = set()
    if not target_ng_datablock or not isinstance(target_ng_datablock, bpy.types.NodeTree) or not target_ng_datablock.is_node_group:
        return []

    # 内部递归函数
    def check_tree_for_target_nodegroup(current_tree, target_datablock, visited_trees):
        if not current_tree or current_tree.name_full in visited_trees: # 使用 name_full 以处理库数据
            return False
        visited_trees.add(current_tree.name_full)
        for node in current_tree.nodes:
            if node.type == 'GROUP':
                if node.node_tree == target_datablock:
                    return True
                if node.node_tree and check_tree_for_target_nodegroup(node.node_tree, target_datablock, visited_trees):
                    return True
        return False

    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree:
            visited_trees_for_this_material_check = set()
            if check_tree_for_target_nodegroup(mat.node_tree, target_ng_datablock, visited_trees_for_this_material_check):
                materials_found.add(f"材质 '{mat.name}'")
    return sorted(list(materials_found))

# --- 辅助函数：获取数据块的用户信息 ---
def get_datablock_users_info(datablock):
    users_info = []
    if not datablock:
        return ["无效的数据块"]

    # 1. 图片纹理的典型用户
    if isinstance(datablock, bpy.types.Image):
        for mat in bpy.data.materials:
            if mat.use_nodes and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image == datablock:
                        users_info.append(f"材质 '{mat.name}' (节点: '{node.name}')")
        for tex in bpy.data.textures: # Legacy textures
            if tex.type == 'IMAGE' and tex.image == datablock:
                users_info.append(f"旧版纹理 '{tex.name}'")
        # TODO: 补充笔刷、Grease Pencil 等的用户检查

    # 2. 节点组的典型用户 (主要材质)
    elif isinstance(datablock, bpy.types.NodeTree) and datablock.is_node_group:
        users_info.extend(find_materials_using_nodegroup_for_report(datablock))
        # 检查其他节点组是否使用了此节点组
        for ng in bpy.data.node_groups:
            if ng == datablock: continue
            if ng.users > 0: # 仅检查仍有用户的节点组
                for node in ng.nodes:
                    if node.type == 'GROUP' and node.node_tree == datablock:
                        users_info.append(f"节点组 '{ng.name}' (内部节点: '{node.name}')")
                        break # 找到一个即可

    # 3. 对象的典型用户 (修改器、约束、父子关系等)
    elif isinstance(datablock, bpy.types.Object):
        for obj_user in bpy.data.objects:
            if obj_user == datablock: continue
            # 修改器
            for mod in obj_user.modifiers:
                props_to_check = ['object', 'target', 'cage_object', 'influence_object', 'target_object'] # 常见物体引用属性
                for prop_name in props_to_check:
                    if hasattr(mod, prop_name) and getattr(mod, prop_name) == datablock:
                        users_info.append(f"物体 '{obj_user.name}' (修改器: '{mod.name}', 属性: '{prop_name}')")
            # 约束
            for const in obj_user.constraints:
                if hasattr(const, 'target') and const.target == datablock:
                    users_info.append(f"物体 '{obj_user.name}' (约束: '{const.name}')")
                # 某些约束有多个目标，例如 Damped Track 的 head_tail
                if hasattr(const, 'targets'):
                    for t_item in const.targets:
                        if hasattr(t_item, 'target') and t_item.target == datablock: # e.g. Follow Path, Track To
                            users_info.append(f"物体 '{obj_user.name}' (约束: '{const.name}', 子目标)")
                            break
            # 父子关系 (如果 datablock 是父级)
            if obj_user.parent == datablock:
                users_info.append(f"物体 '{obj_user.name}' (作为其子级)")
        # 集合实例
        if datablock.instance_type == 'COLLECTION' and datablock.instance_collection:
             users_info.append(f"物体 '{datablock.name}' 自身实例化了集合 '{datablock.instance_collection.name}'")


    # 4. 材质的典型用户 (物体上的材质槽)
    elif isinstance(datablock, bpy.types.Material):
        for obj in bpy.data.objects:
            if obj.active_material == datablock: # 活动材质
                users_info.append(f"物体 '{obj.name}' (活动材质)")
            for slot in obj.material_slots: # 所有材质槽
                if slot.material == datablock:
                    users_info.append(f"物体 '{obj.name}' (材质槽: '{slot.name if slot.name else '未命名槽'}')")
                    break # 对于一个物体，找到一个槽即可

    # 5. 集合的典型用户 (场景主集合，物体实例化的集合)
    elif isinstance(datablock, bpy.types.Collection):
        for scene in bpy.data.scenes:
            if scene.collection == datablock:
                users_info.append(f"场景 '{scene.name}' (作为主场景集合)")
        for obj in bpy.data.objects:
            if obj.is_instancer and obj.instance_type == 'COLLECTION' and obj.instance_collection == datablock:
                users_info.append(f"物体 '{obj.name}' (实例化此集合)")


    # 通用用户数回退 (如果上面没有特定检查或找不到用户)
    if not users_info and hasattr(datablock, 'users') and datablock.users > 0:
        users_from_map_display = []
        if hasattr(datablock, 'user_map'): # Blender 3.0+
            try:
                # user_map 键可能是 ID 或 (ID, subtype_index)
                for user_id_key in datablock.user_map(subset={datablock}).keys(): # subset to itself to get actual users
                    user_id = user_id_key if isinstance(user_id_key, bpy.types.ID) else user_id_key[0]
                    if user_id: # 确保 user_id 有效
                         users_from_map_display.append(f"'{user_id.name_full}' (类型: {type(user_id).__name__})")
            except Exception as e:
                print(f"    警告: 检查 '{datablock.name_full}' 的 user_map 时出错: {e}")

        if users_from_map_display:
            display_count = 3
            users_text = ', '.join(users_from_map_display[:display_count])
            if len(users_from_map_display) > display_count:
                users_text += ' 等...'
            users_info.append(f"有 {datablock.users} 个直接用户，包括: {users_text}")
        else:
            users_info.append(f"有 {datablock.users} 个直接用户 (详细信息需更深入的特定检查)。")


    return users_info if users_info else ["通过此脚本的检查未找到特定用户。"]


# --- 主函数：查找所有丢失资产及其用户 ---
def find_all_missing_assets_and_users():
    print("开始检查Blend文件中的丢失资产...")
    missing_assets_report = {} # 字典: { "丢失资产ID": ["用户1信息", "用户2信息"] }
    checked_missing_datablocks = set() # 存储已报告的丢失数据块名称，避免重复报告（特别是链接数据）

    # 1. 检查丢失的图片纹理
    print("\n--- 正在检查丢失的图片纹理 ---")
    for image in bpy.data.images:
        if image.name_full in checked_missing_datablocks: continue
        if image.source == 'FILE' and image.packed_file is None:
            try:
                filepath_abs = bpy.path.abspath(image.filepath_from_user())
                if not filepath_abs or not os.path.exists(filepath_abs):
                    asset_id = f"图片: '{image.name_full}' (预期路径: {image.filepath_from_user()})"
                    print(f"  丢失: {asset_id}")
                    missing_assets_report[asset_id] = get_datablock_users_info(image)
                    checked_missing_datablocks.add(image.name_full)
            except Exception as e:
                print(f"  检查图片 '{image.name_full}' 时出错: {e}")


    # 2. 检查丢失的链接库文件
    print("\n--- 正在检查丢失的链接库文件 ---")
    missing_library_files = set() # 存储确认丢失的库文件路径
    for lib in bpy.data.libraries:
        if lib.name_full in checked_missing_datablocks: continue
        try:
            lib_filepath_abs = bpy.path.abspath(lib.filepath)
            if not os.path.exists(lib_filepath_abs):
                asset_id = f"链接库文件: '{lib.name_full}' (预期路径: {lib.filepath})"
                print(f"  丢失: {asset_id}")
                missing_assets_report[asset_id] = [f"所有从此库链接的数据块都将受影响。"]
                missing_library_files.add(lib.filepath) # 使用原始记录的路径进行比较
                checked_missing_datablocks.add(lib.name_full)
        except Exception as e:
            print(f"  检查库 '{lib.name_full}' 时出错: {e}")


    # 3. 检查可能从(已找到或已丢失的)库中断开链接的数据块
    print("\n--- 正在检查可能断开链接的数据块 (例如对象、节点组等) ---")
    # 遍历所有可能链接的数据块类型
    id_collections_to_check = [
        bpy.data.objects, bpy.data.materials, bpy.data.node_groups,
        bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras,
        bpy.data.actions, bpy.data.armatures, bpy.data.collections,
        # bpy.data.worlds, bpy.data.scenes (场景和世界通常不会以这种方式“丢失”其库，但可以检查)
    ]
    for id_collection in id_collections_to_check:
        for db in id_collection:
            if db.name_full in checked_missing_datablocks: continue
            if db.library: # 如果它是一个链接的数据块
                is_from_known_missing_lib = db.library.filepath in missing_library_files
                problem_description = None

                if is_from_known_missing_lib:
                    problem_description = f"链接数据块 (来自确认丢失的库 '{db.library.filepath}')"
                else:
                    # 即使库文件存在，数据块本身也可能在库文件中丢失 (例如，被删除或重命名)
                    # 这是一个较难通用检测的情况，但有些启发式方法：
                    if isinstance(db, bpy.types.Object) and \
                       db.type not in {'EMPTY', 'ARMATURE', 'LATTICE', 'CAMERA', 'LIGHT', 'SPEAKER', 'GPENCIL'} and \
                       db.data is None and \
                       db.is_library_indirect: # 确保它是间接链接的
                        problem_description = f"链接对象但无数据 (可能从库 '{db.library.filepath}' 中丢失定义)"
                    
                    # 对于节点组，如果它被链接，但行为像丢失的 (例如，导致错误或UI中显示异常)
                    # 之前用户的案例是：NodeGroup在bpy.data.node_groups中，但从其库中丢失。
                    # 如果一个链接的节点组 (db.library is not None) 有用户，但其内容无法解析，则有问题。
                    # 这个脚本主要依赖于数据块本身的 "存在但无效" 状态。
                    # Blender 的 "Report Missing Files" 对这类情况更敏感。

                if problem_description:
                    asset_id = f"{problem_description}: '{db.name_full}' (类型: {type(db).__name__})"
                    print(f"  问题: {asset_id}")
                    missing_assets_report[asset_id] = get_datablock_users_info(db)
                    checked_missing_datablocks.add(db.name_full)


    # 4. 检查丢失的影片剪辑
    print("\n--- 正在检查丢失的影片剪辑 ---")
    for mc in bpy.data.movieclips:
        if mc.name_full in checked_missing_datablocks: continue
        if mc.source == 'FILE':
            try:
                filepath_abs = bpy.path.abspath(mc.filepath)
                if not filepath_abs or not os.path.exists(filepath_abs):
                    asset_id = f"影片剪辑: '{mc.name_full}' (预期路径: {mc.filepath})"
                    print(f"  丢失: {asset_id}")
                    users = [] # 影片剪辑主要用在运动跟踪、合成节点、纹理节点
                    for scene in bpy.data.scenes:
                        if scene.active_clip == mc: users.append(f"场景 '{scene.name}' (活动剪辑)")
                    for mat in bpy.data.materials: # 检查材质节点
                        if mat.use_nodes and mat.node_tree:
                            for node in mat.node_tree.nodes:
                                if node.type == 'TEX_MOVIE' and node.clip == mc : # Movie Clip Node (Cycles/EEVEE)
                                    users.append(f"材质 '{mat.name}' (节点 '{node.name}')")
                                elif hasattr(node, 'movie_clip') and node.movie_clip == mc: # e.g. some compositor nodes
                                     users.append(f"材质/合成 '{mat.name}' (节点 '{node.name}')")

                    # 检查合成器节点
                    for scene in bpy.data.scenes:
                        if scene.use_nodes and scene.node_tree:
                             for node in scene.node_tree.nodes:
                                if (node.type == 'MOVIECLIP' or hasattr(node, 'clip')) and node.clip == mc:
                                    users.append(f"场景 '{scene.name}' 合成器 (节点 '{node.name}')")
                    missing_assets_report[asset_id] = users if users else get_datablock_users_info(mc) # 回退到通用检查
                    checked_missing_datablocks.add(mc.name_full)
            except Exception as e:
                print(f"  检查影片剪辑 '{mc.name_full}' 时出错: {e}")


    # 5. 检查丢失的声音文件
    print("\n--- 正在检查丢失的声音文件 ---")
    for sound in bpy.data.sounds:
        if sound.name_full in checked_missing_datablocks: continue
        if not sound.is_packed:
            try:
                filepath_abs = bpy.path.abspath(sound.filepath)
                if not filepath_abs or not os.path.exists(filepath_abs):
                    asset_id = f"声音文件: '{sound.name_full}' (预期路径: {sound.filepath})"
                    print(f"  丢失: {asset_id}")
                    users = [] # 声音主要用在序列编辑器、扬声器对象
                    for scene in bpy.data.scenes:
                        if scene.sequence_editor and scene.sequence_editor.sequences:
                            for strip in scene.sequence_editor.sequences:
                                if strip.type == 'SOUND' and strip.sound == sound:
                                    users.append(f"序列编辑器 (场景 '{scene.name}', 序列 '{strip.name}')")
                    for obj in bpy.data.objects:
                        if obj.type == 'SPEAKER' and obj.data and obj.data.sound == sound:
                            users.append(f"扬声器对象 '{obj.name}'")
                    missing_assets_report[asset_id] = users if users else get_datablock_users_info(sound)
                    checked_missing_datablocks.add(sound.name_full)
            except Exception as e:
                print(f"  检查声音 '{sound.name_full}' 时出错: {e}")

    # 6. 检查丢失的字体文件
    print("\n--- 正在检查丢失的字体文件 ---")
    for font in bpy.data.fonts:
        if font.name_full in checked_missing_datablocks: continue
        if font.filepath: # 默认字体 filepath 为空
            try:
                filepath_abs = bpy.path.abspath(font.filepath)
                if not os.path.exists(filepath_abs):
                    asset_id = f"字体文件: '{font.name_full}' (预期路径: {font.filepath})"
                    print(f"  丢失: {asset_id}")
                    users = []
                    for obj in bpy.data.objects:
                        if obj.type == 'FONT' and obj.data and obj.data.font == font:
                            users.append(f"文本对象: '{obj.name}'")
                    # 字体也可能用在 VSE 的文本条中
                    for scene in bpy.data.scenes:
                        if scene.sequence_editor and scene.sequence_editor.sequences:
                            for strip in scene.sequence_editor.sequences:
                                if strip.type == 'TEXT' and hasattr(strip, 'font') and strip.font == font: # Effect Strip Text
                                     users.append(f"序列编辑器 (场景 '{scene.name}', 文本序列 '{strip.name}')")
                    missing_assets_report[asset_id] = users if users else ["通过此脚本的检查未找到特定用户。"]
                    checked_missing_datablocks.add(font.name_full)
            except Exception as e:
                print(f"  检查字体 '{font.name_full}' 时出错: {e}")


    # --- 打印最终报告 ---
    print("\n\n--- 丢失资产及其引用者报告 ---")
    if missing_assets_report:
        for asset_id, users in missing_assets_report.items():
            print(f"\n[!] 丢失或有问题的资产: {asset_id}")
            if users:
                print("  被以下资源引用:")
                for user_info in users:
                    print(f"  - {user_info}")
            else:
                print("  - 通过此脚本的检查未找到特定的直接引用者 (或者它是一个库文件，影响间接)。")
    else:
        print("在此文件中未检测到明确丢失的外部文件或严重损坏的链接数据块。")

    print("\n\n--- 建议 ---")
    print("为进行更全面的检查，请同时使用Blender的内置工具:")
    print("- File (文件) > External Data (外部数据) > Report Missing Files (报告丢失的文件) - 这会生成一个文本块列出所有Blender能检测到的丢失文件。")
    print("- File (文件) > External Data (外部数据) > Find Missing Files (查找丢失的文件) - 尝试自动重新链接。")
    print("大纲视图 (Outliner) 的 'Blender File' (Blender 文件) 或 'Orphan Data' (孤立数据) 模式有时也能帮助发现问题。")
    print("此脚本主要关注文件路径是否存在以及一些常见链接问题，可能无法覆盖所有类型的内部数据损坏。")



class ShowMissingAssetsOperator(bpy.types.Operator):
    bl_idname = "cat.show_missing_assets"
    bl_label = "Show Missing Assets"

    def execute(self, context):
        find_all_missing_assets_and_users()
        return {"FINISHED"}

