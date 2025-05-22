import bpy
from mathutils import Vector
import addon_utils

#constants

ADDON_NAME = "Conceptart Tools"
for mod in addon_utils.modules():
    if mod.bl_info['name'] == ADDON_NAME:
        filepath = mod.__file__
        path=filepath.split("\__init__.py")[0]
        path=path.replace("\\","/")
        preset_path=path + "/PresetFiles/Presets.blend"
GROUP_MOD="CAT_MeshGroup"
MIRROR_MOD="CAT_Mirror"
ARRAY_MOD="CAT_Array"
GROUP_NODE="MeshGroup"
INST_PREFIX="Inst_"
CUSTOM_NAME="CAT"
PIVOT_NAME="CAT_Inst_Pivot"
INSTANCE_NAME="CAT_Inst"
TEMP_MESH="cat_meshgruop_tempmesh"
OFFSET_ATTR="CAT_Offset"
WORLD_ORIGIN=Vector((0,0,0))

#functions
def import_node_group(file_path, node_name) -> bpy.types.NodeGroup:
    """从文件载入NodeGroup"""

    INNER_PATH = "/NodeTree"
    FULL_PATH=str(file_path) + INNER_PATH
    node_exist = False
    for node in bpy.data.node_groups:
        if node_name not in node.name:
            node_exist = False
        else:
            node_exist = True
            node_import = node
            break

    if node_exist is False:  # 如果没有导入，导入
        bpy.ops.wm.append(
            filepath=str(file_path),
            directory=FULL_PATH,
            filename=node_name,
        )

    for node in bpy.data.node_groups:
        if node.name == node_name:
            node_import = node
            break

    return node_import

def add_meshgroup_modifier(mesh,target_group=None,offset=Vector((0,0,0))): 
    """添加Geometry Nodes MeshGroup Modifier"""

    check_modifier = False
    # print(mesh.location)
    offset=WORLD_ORIGIN - offset

    print("offset",offset)

    for modifier in mesh.modifiers:
        if modifier.name == GROUP_MOD:
            check_modifier = True
            break

    if check_modifier is False:
        geo_node_modifier = mesh.modifiers.new(
            name=GROUP_MOD, type="NODES"
        )
        geo_node_modifier.node_group = bpy.data.node_groups[GROUP_NODE]
    else:
        geo_node_modifier = mesh.modifiers[GROUP_MOD]
        geo_node_modifier.node_group = bpy.data.node_groups[GROUP_NODE]

    #set Collection Instance to target group
    geo_node_modifier["Socket_2"]=target_group
    #set offset
    geo_node_modifier["Socket_7"]=offset

def add_mirror_modifier(mesh,axis=0):
    """添加DataTransfer Modifier传递顶点色"""

    # proxy_object = bpy.data.objects[TRANSFERPROXY_PREFIX + mesh.name]
    check_modifier = False
    pivot_object=mesh.parent

    for modifier in mesh.modifiers:  # 检查是否有modifier
        if modifier.name == MIRROR_MOD:
            check_modifier = True
            break

    if check_modifier is False:  # 如果没有则添加
        mirror_modifier = mesh.modifiers.new(
            name=MIRROR_MOD, type="MIRROR"
        )
        mirror_modifier.mirror_object = pivot_object
        mirror_modifier.use_axis[axis] = True
        mirror_modifier.use_bisect_axis[axis] = True
        mirror_modifier.use_mirror_merge = True

def add_array_modifier(mesh):
    """添加Array Modifier"""
    check_modifier = False

    for modifier in mesh.modifiers:  # 检查是否有modifier
        if modifier.name == ARRAY_MOD:
            check_modifier = True
            break

    if check_modifier is False:  # 如果没有则添加
        array_modifier = mesh.modifiers.new(
            name="CAT_Array", type="ARRAY"
        )
        # array_modifier.use_merge_vertices = True
        # array_modifier.use_merge_vertices_cap = True

def realize_meshgroup_modifier(mesh,realize=True):
    """Realize Geometry Nodes MeshGroup Modifier"""
    #check if the mesh has the modifier
    check_modifier = False

    for modifier in mesh.modifiers:
        if modifier.name == GROUP_MOD:
            check_modifier = True
            geo_node_modifier = mesh.modifiers[GROUP_MOD]
            geo_node_modifier["Socket_3"]=realize
            break

    if check_modifier is False:
        print("Mesh does not have the MeshGroup modifier")
        return

def check_is_meshgroup_inst(obj):
    is_meshgroup=False

    if obj.type == 'MESH':
        try:
            if obj[CUSTOM_NAME]==INSTANCE_NAME:
                #if has mesh group modifier
                for modifier in obj.modifiers:
                    if modifier.type == 'NODES':
                        if modifier.node_group.name == GROUP_NODE:
                            is_meshgroup=True
        except:
            pass
    return is_meshgroup


def find_objs_bb_center(objs):
    ## Find the center of the bounding box of all objects

    all_coords = []
    for o in objs:
        bb = o.bound_box
        mat = o.matrix_world
        for vert in bb:
            coord = mat @ Vector(vert)
            all_coords.append(coord)

    if not all_coords:
        return Vector((0, 0, 0))

    center = sum(all_coords, Vector((0, 0, 0))) / len(all_coords)
    return center

def find_objs_bb_lowest_center(objs):
    ## Find the lowest_center of the bounding box of all objects

    all_coords = []
    for o in objs:
        bb = o.bound_box
        mat = o.matrix_world
        for vert in bb:
            coord = mat @ Vector(vert)
            all_coords.append(coord)

    if not all_coords:
        return Vector((0, 0, 0))

    # Find the lowest Z value among all bounding box coordinates
    lowest_z = min(coord.z for coord in all_coords)
    # Find the center in X and Y
    center_xy = sum((Vector((coord.x, coord.y, 0)) for coord in all_coords), Vector((0, 0, 0))) / len(all_coords)
    center = Vector((center_xy.x, center_xy.y, lowest_z))
    return center

