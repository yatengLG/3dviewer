# -*- coding: utf-8 -*-
# @Author  : LG

import open3d as o3d
from open3d.visualization import gui, rendering
import numpy as np
import platform
import laspy
import os
import yaml

cwd = os.getcwd()


class LableLUT:
    class Label:
        def __init__(self, name, value, color):
            self.name = name
            self.value = value
            self.color = color

    def __init__(self, colors):
        self.colors = colors
        self.labels = {}
        self.index = 0

    def add_label(self, value, label, color=None):
        if color is None:
            if self.index < len(self.colors):
                color = self.colors[self.index]
                self.index += 1
            else:
                color = self
        self.labels[value] = self.Label(label, value, color)


class MaterialPanel(gui.CollapsableVert):
    def __init__(self, tfs):
        super(MaterialPanel, self).__init__('View Setting', 0.25 * tfs, gui.Margins(tfs, 0, tfs, 0))
        grid = gui.VGrid(2, 0.25 * tfs)
        self.add_child(grid)
        # show axes
        self.show_axes = gui.ToggleSwitch('')
        grid.add_child(gui.Label('Show axes'))
        grid.add_child(self.show_axes)

        # bg color
        self.bg_color_edit = gui.ColorEdit()
        grid.add_child(gui.Label('BG color'))
        grid.add_child(self.bg_color_edit)

        # point size
        self.point_size_slider = gui.Slider(gui.Slider.INT)
        self.point_size_slider.set_limits(1, 10)
        grid.add_child(gui.Label('Point Size'))
        grid.add_child(self.point_size_slider)


class ClassificationPanel(gui.CollapsableVert):
    def __init__(self, tfs):
        super(ClassificationPanel, self).__init__('Classification', 0.25 * tfs, gui.Margins(tfs, 0, tfs, 0))
        self._label2color = {}
        self.geometry_color_callback = None # 回调函数
        self.geometry_check_callback = None

        self.tree = gui.TreeView()
        self.add_child(self.tree)

    def regist_geometry_color_callback(self, callback):
        self.geometry_color_callback = callback

    def regist_geometry_show_callback(self, callback):
        self.geometry_check_callback = callback

    def set_labels(self, labellut):
        """
        :param labellut:    LableLUT.labels -> {index:Lable(label, value, color)}
        :return:
        """
        self.tree.clear()
        root = self.tree.get_root_item()
        for index in sorted(labellut.labels.keys()):
            label = labellut.labels[index]
            color = label.color
            if len(color) == 3:
                color += [1.0]
            self._label2color[index] = color
            color = gui.Color(color[0], color[1], color[2])
            cell = gui.LUTTreeCell(str(index) + ": " + label.name, True, color, None, None)
            cell.checkbox.set_on_checked(self._make_on_checked(index, self._on_label_checked))
            cell.color_edit.set_on_value_changed(self._make_on_color_changed(index, self._on_label_color_changed))
            self.tree.add_item(root, cell)

    def get_color(self):
        return [self._label2color[index] for index in sorted(self._label2color.keys())] # 按顺序输出index对应的颜色列表

    def _make_on_checked(self, index, func):
        def on_checked(checked):
            func(index, checked)
        return on_checked

    def _on_label_checked(self, index, checked):
        if self.geometry_check_callback is not None:
            self.geometry_check_callback(index, checked)

    def _make_on_color_changed(self, index, func):
        def color_change(color):
            func(color, index)
        return color_change

    def _on_label_color_changed(self, color, index):
        self._label2color[index] = [
            color.red, color.green, color.blue,
            self._label2color[index][3]
        ]
        if self.geometry_color_callback is not None:
            self.geometry_color_callback(index, self._label2color[index])


class ToolsPanel(gui.Vert):
    def __init__(self, tfs):
        super(ToolsPanel, self).__init__()
        # view control panel
        self.material_panel = MaterialPanel(tfs)
        self.add_child(self.material_panel)

        self.classification_panel = ClassificationPanel(tfs)
        self.add_child(self.classification_panel)


# class LabelLut:
#     class Label:
#         def __init__(self, name, value, color):
#             self.name = name
#             self.value = value
#             self.color = color
#
#     def __init__(self, lut_colors):
#         self._next_color = 0
#         self.labels = {}
#         self.Colors = lut_colors
#
#     def add_label(self, name, value, color=None):
#         """Adds a label to the table.
#
#         **Example:**
#             The following sample creates a LUT with 3 labels::
#
#                 lut = ml3d.vis.LabelLUT()
#                 lut.add_label('one', 1)
#                 lut.add_label('two', 2)
#                 lut.add_label('three', 3, [0,0,1]) # use blue for label 'three'
#
#         **Args:**
#             name: The label name as string.
#             value: The value associated with the label.
#             color: Optional RGB color. E.g., [0.2, 0.4, 1.0].
#         """
#         if color is None:
#             if self._next_color >= len(self.Colors):
#                 color = [0.85, 1.0, 1.0]
#             else:
#                 color = self.Colors[self._next_color]
#                 self._next_color += 1
#         self.labels[value] = self.Label(name, value, color)


class AppWindow:
    OPEN_FILE = 11
    QUIT = 12
    TOOLS = 21
    SAVESETTING = 22
    Instructions = 31
    ABOUT = 32

    def __init__(self):
        self.setting = None
        self.pointcloud = None
        self.classification = None

        self.window = gui.Application.instance.create_window("3DViewer", 1280, 720)
        tfs = self.window.theme.font_size
        self.scene_widget = gui.SceneWidget()
        self.scene_widget.scene = rendering.Open3DScene(self.window.renderer)
        self.scene_widget.set_on_key(self._keyboard_event)
        self.window.add_child(self.scene_widget)

        self.materials = [None]
        self.gradient = rendering.Gradient()
        # menu
        menu = gui.Menu()
        gui.Application.instance.menubar = menu

        menu_file = gui.Menu()
        menu_file.add_item('Open file', self.OPEN_FILE)
        self.window.set_on_menu_item_activated(self.OPEN_FILE, self._open_file)
        menu_file.add_item('Quit', self.QUIT)
        self.window.set_on_menu_item_activated(self.QUIT, self._quit)
        menu.add_menu('File', menu_file)

        menu_tools = gui.Menu()
        menu_tools.add_item('Tools panel', self.TOOLS)
        self.window.set_on_menu_item_activated(self.TOOLS, self._tools_bar_show)
        menu_tools.add_item('Save setting', self.SAVESETTING)
        self.window.set_on_menu_item_activated(self.SAVESETTING, self._upgrade_config_yaml)
        menu_tools.set_checked(self.TOOLS, True)
        menu.add_menu('Tools', menu_tools)

        menu_help = gui.Menu()
        menu_help.add_item('Instructions', self.Instructions)
        self.window.set_on_menu_item_activated(self.Instructions, self._instructions_doc)
        menu_help.add_item('About', self.ABOUT)
        self.window.set_on_menu_item_activated(self.ABOUT, self._about_doc)
        menu.add_menu('Help', menu_help)

        self.tools_panel = ToolsPanel(tfs)
        self.tools_panel.material_panel.show_axes.set_on_clicked(self._show_axes)
        self.tools_panel.material_panel.point_size_slider.set_on_value_changed(self._change_point_size)
        self.tools_panel.material_panel.bg_color_edit.set_on_value_changed(self._change_bg_color)
        self.tools_panel.classification_panel.regist_geometry_color_callback(self._change_geometry_color)
        self.tools_panel.classification_panel.regist_geometry_show_callback(self._change_geometry_show)
        self.window.add_child(self.tools_panel)

        self.info = gui.Label('')
        self.window.add_child(self.info)

        self.apply_setting()
        self.window.set_on_layout(self._on_layout)

    def apply_setting(self):
        with open(os.path.join(cwd, 'config.yaml'), 'r', encoding="utf-8") as f:
            self.setting = yaml.load(f, Loader=yaml.FullLoader)
        self.scene_widget.scene.set_background(self.setting['background_color'])

        # self.tools_panel.material_panel.point_size_slider. = self.setting['pointsize']
        lablut = LableLUT(self.setting['lut_colors'])
        for i, c in enumerate(self.setting['classes']):
            lablut.add_label(i, c)

        self.tools_panel.classification_panel.set_labels(lablut)

        self.materials = [rendering.Material() for _ in range(len(self.setting['classes']))]

        for i, material in enumerate(self.materials):
            material.point_size = self.setting['pointsize']
            material.base_color = self.tools_panel.classification_panel.get_color()[i]

    def _on_layout(self, layout_context):
        r = self.window.content_rect
        self.scene_widget.frame = r
        width = 22 * layout_context.theme.font_size
        height = min(r.height, self.tools_panel.calc_preferred_size(
            layout_context, gui.Widget.Constraints()).height)
        self.tools_panel.frame = gui.Rect(r.get_right() - width, r.y, width, height)

        self.info.frame =gui.Rect(r.get_left(),
                                  r.get_bottom() - self.window.theme.font_size,
                                  r.get_right()-r.get_left(),
                                  self.window.theme.font_size)

    def _open_file(self):
        dlg = gui.FileDialog(gui.FileDialog.OPEN, '选择文件', self.window.theme)
        dlg.add_filter(
            ".xyz .xyzc .ply .pcd .pts .las",
            "Point cloud files (.xyz, .xyzc .xyzn, .xyzrgb, .ply, "
            ".pcd, .pts, .las)")

        dlg.add_filter("", "All files")
        dlg.set_on_cancel(self._file_dialog_cancel)
        dlg.set_on_done(self._open_file_dialog_done)
        self.window.show_dialog(dlg)

    def _open_file_dialog_done(self, path):
        self.window.close_dialog()
        self._load_file(path)

    def _load_file(self, path:str):
        self.scene_widget.scene.clear_geometry()

        if path.endswith('.las'):
            pointcloud, classification = self._load_las(path)
        else:
            pointcloud = o3d.io.read_point_cloud(path)
            classification = None
            label_file = path.split('.')[0]+'_classification.txt'
            if os.path.exists(label_file):
                try:
                    with open(label_file, 'r') as f:
                        classification = np.array([int(l.rstrip('\n')) for l in f.readlines()], dtype=np.int16)
                except Exception as e:
                    print('[Read classification faild!] {}'.format(e))
        self.pointcloud = pointcloud
        self.classification = classification

        bounds = pointcloud.get_axis_aligned_bounding_box()
        self.scene_widget.setup_camera(60, bounds, bounds.get_center())

        print(self.pointcloud)
        print(self.classification)

        if self.classification is None:
            self.scene_widget.scene.add_geometry('__pointcloud-0__', self.pointcloud, self.materials[0])
            self.tools_panel.classification_panel.visible = False
            self.info.text = "{} | {} | no classification!".format(os.path.split(path)[-1], pointcloud)

        else:
            self._upgrade_geometry_color()
            # self.materials[0].shader = 'defaultUnlit'
            self.tools_panel.classification_panel.visible = True
            self.info.text = "{} | {}".format(os.path.split(path)[-1], pointcloud)

    def _load_las(self, path):
        f =  laspy.read(path)
        points = np.vstack([f.x, f.y, f.z]).transpose()
        classification = np.array(f.classification)
        pointcloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
        return pointcloud, classification

    def _upgrade_geometry_color(self, index=None, color=None):

        def _upgrade_one_geometry(index, color):
            if index >= len(self.tools_panel.classification_panel.get_color()):
                self._message_dialog('Warning', '类别必须是从0开始的连续数值')
                self.scene_widget.scene.clear_geometry()
                return
            if color is not None:
                self.materials[index].base_color = color
            else:
                self.materials[index].base_color = self.tools_panel.classification_panel.get_color()[index]

            if self.pointcloud is None:
                return

            geometry_name = '__pointcloud-{}__'.format(index)
            if not self.scene_widget.scene.has_geometry(geometry_name):
                pointcloud = self.pointcloud.select_by_index(np.arange(len(self.classification))[self.classification == index])
                print(index, pointcloud)
                print(index, np.asarray(pointcloud.points) )
                print(index, geometry_name)
                print(index, self.materials[index])
                self.scene_widget.scene.add_geometry(geometry_name, pointcloud, self.materials[index])
            else:
                self.scene_widget.scene.modify_geometry_material(geometry_name, self.materials[index])

        if index is None:
            if self.classification is None:
                return
            for c in set(self.classification):
                _upgrade_one_geometry(c, color)
        else:
            _upgrade_one_geometry(index, color)

    def _file_dialog_cancel(self):
        self.window.close_dialog()

    def _quit(self):
        gui.Application.instance.quit()

    def _tools_bar_show(self):
        checked = gui.Application.instance.menubar.is_checked(self.TOOLS)

        self.tools_panel.visible = not checked
        gui.Application.instance.menubar.set_checked(self.TOOLS, not checked)

    def _upgrade_config_yaml(self):
        s = yaml.dump(self.setting)
        with open(os.path.join(cwd, 'config.yaml'), 'w') as f:
            f.write(s)

    def _instructions_doc(self):
        self._message_dialog('Instructions', "1. 类别配置，可通过对config.yaml中classes进行更改获得\n"
                                             "   类别文件存放于点云文件同目录下，命名为'点云文件名_classification.txt'"
                                             "  （需注意的是，类别名为任意字符串，类别标签为从0开始的连续整数）\n"
                                             "2. 可通过调整背景颜色和点大小使点云更加明显\n"
                                             "3. 可通过键盘x、y、z快速调整视角\n"
                                             "4. 对于只有一个点的点云，会发生未知错误，正在修改"
                                             "5. 后续功能待添加......")

    def _about_doc(self):
        self._message_dialog('About', 'Author: LG\n'
                                      'Email : yatenglg@qq.com')

    def _show_axes(self, check):
        print('show axes', check)
        self.scene_widget.scene.show_axes(check)

    def _change_point_size(self, point_size):
        for index in range(len(self.materials)):
            self.materials[index].point_size = point_size
            geometry_name = '__pointcloud-{}__'.format(index)
            if self.scene_widget.scene.has_geometry(geometry_name):
                self.scene_widget.scene.modify_geometry_material(geometry_name, self.materials[index])
        self.setting['pointsize'] = point_size

    def _change_bg_color(self, new_color):
        self.scene_widget.scene.set_background([new_color.red, new_color.green, new_color.blue, new_color.alpha])
        self.setting['background_color'] = [new_color.red, new_color.green, new_color.blue, new_color.alpha]

    def _change_geometry_color(self, index, color):
        self.setting['lut_colors'][index] = color
        self._upgrade_geometry_color(index, color)

    def _change_geometry_show(self, index, checked):
        geometry_name = '__pointcloud-{}__'.format(index)
        self.scene_widget.scene.show_geometry(geometry_name, checked)

    def _message_dialog(self, title, message, ok_callback=None):
        dlg = gui.Dialog(title)

        tfs = self.window.theme.font_size
        dlg_layout = gui.Vert(tfs, gui.Margins(tfs, tfs, tfs, tfs))
        dlg_layout.add_child(gui.Label(message))

        ok_button = gui.Button("Ok")
        if ok_callback is not None:
            ok_button.set_on_clicked(ok_callback)
        else:
            ok_button.set_on_clicked(self.window.close_dialog)

        button_layout = gui.Horiz()
        button_layout.add_stretch()
        button_layout.add_child(ok_button)

        dlg_layout.add_child(button_layout)
        dlg.add_child(dlg_layout)
        self.window.show_dialog(dlg)

    def _keyboard_event(self, event):
        if self.pointcloud is None:
            return gui.Widget.EventCallbackResult.IGNORED

        aabb = self.pointcloud.get_axis_aligned_bounding_box()
        center = aabb.get_center()
        m = max([0, 0, max(aabb.max_bound - aabb.min_bound)])

        if event.type == gui.KeyEvent.Type.DOWN:
            if event.key == 120:    # x
                self.scene_widget.look_at(center, center + [m, 0, 0], [0, 0, 1])

            if event.key == 121:    # y
                self.scene_widget.look_at(center, center + [0, m, 0], [0, 0, 1])

            if event.key == 122:    # z
                self.scene_widget.look_at(center, center + [0, 0, m], [0, 1, 0])

            return gui.Widget.EventCallbackResult.HANDLED
        return gui.Widget.EventCallbackResult.IGNORED


def main():
    if platform.system() == "Darwin":
        serif = "Times New Roman"
        hanzi = "STHeiti Light"

    elif platform.system() == "Windows":
        serif = "c:/windows/fonts/times.ttf"  # Times New Roman
        hanzi = "c:/windows/fonts/msyh.ttc"  # YaHei UI

    else:
        serif = "DejaVuSerif"
        hanzi = "NotoSansCJK"

    font = gui.FontDescription(serif)
    font.add_typeface_for_language(hanzi, "zh")

    app = gui.Application.instance
    app.initialize()

    app.set_font(gui.Application.DEFAULT_FONT_ID, font)

    AppWindow()
    app.run()


if __name__ == '__main__':
    main()
