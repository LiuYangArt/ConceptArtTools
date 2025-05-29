import bpy

# 获取当前选中的数据块（从 Outliner 中选中）
def get_selected_datablock():
    # 获取 Outliner 的上下文
    for area in bpy.context.screen.areas:
        if area.type == 'OUTLINER':
            for region in area.regions:
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(area=area, region=region):
                        # 获取 Outliner 中选中的数据块
                        if bpy.context.selected_ids:
                            return bpy.context.selected_ids[0]  # 返回第一个选中的 ID（数据块）
    return None

# 查找引用指定数据块的所有用户
def find_users(datablock):
    users = []
    # 遍历所有可能的 Blender 数据块集合
    for collection_name in dir(bpy.data):
        collection = getattr(bpy.data, collection_name)
        # 确保是 bpy_prop_collection 类型（例如 bpy.data.objects, bpy.data.materials 等）
        if isinstance(collection, bpy.types.bpy_prop_collection):
            for item in collection:
                # 检查 item 是否有属性引用了目标数据块
                for prop in dir(item):
                    try:
                        value = getattr(item, prop)
                        # 如果属性值是指向目标数据块的引用
                        if value == datablock:
                            users.append(f"{collection_name}.{item.name}")
                    except (AttributeError, TypeError):
                        continue
    return users


class FindUsersOperator(bpy.types.Operator):
    bl_idname = "cat.find_asset_users"
    bl_label = "Find Asset Users"

    def execute(self, context):
        print("Finding users...")
        selected = get_selected_datablock()
        
        if not selected:
            print("No datablock selected in the Outliner.")
            return
        
        print(f"Selected datablock: {selected.name} (Type: {type(selected).__name__})")
        
        # 查找用户
        users = find_users(selected)
        
        if users:
            print(f"Users of '{selected.name}':")
            for user in users:
                print(f" - {user}")
        else:
            print(f"No users found for '{selected.name}'.")
        return {"FINISHED"}

