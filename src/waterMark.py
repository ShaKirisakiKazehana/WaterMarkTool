import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QDialog,
                             QDialogButtonBox, QSpinBox, QCheckBox, QListWidget, QListWidgetItem)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QIntValidator, QFont, QFontDatabase
from PyQt5.QtCore import Qt

class BatchExportDialog(QDialog):
    """
    自定义对话框，允许用户选择批量输出的文件夹、输出格式和（针对 JPEG）压缩质量。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量输出设置")
        self.selected_format = "JPEG"
        self.output_folder = ""
        self.jpeg_quality = 95

        # 输出格式选择
        format_label = QLabel("输出格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "PNG"])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)

        # 输出文件夹选择
        folder_label = QLabel("输出文件夹:")
        self.folder_line_edit = QLineEdit()
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_folder)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_line_edit)
        folder_layout.addWidget(browse_btn)

        # JPEG质量设置
        quality_label = QLabel("JPEG质量:")
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setEnabled(True)

        # 对话框按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(format_label)
        layout.addWidget(self.format_combo)
        layout.addWidget(folder_label)
        layout.addLayout(folder_layout)
        layout.addWidget(quality_label)
        layout.addWidget(self.quality_spin)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def on_format_changed(self, fmt):
        self.selected_format = fmt
        # 如果选择PNG，则禁用JPEG质量设置
        if fmt == "PNG":
            self.quality_spin.setEnabled(False)
        else:
            self.quality_spin.setEnabled(True)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", "")
        if folder:
            self.folder_line_edit.setText(folder)

    def get_settings(self):
        return {
            "format": self.selected_format,
            "output_folder": self.folder_line_edit.text(),
            "quality": self.quality_spin.value()
        }
    
class FontListDialog(QDialog):
    """
    扫描 C:/Windows/Fonts 下的常见字体文件，并以列表形式显示。
    列表项中展示的是字体预览效果（示例文字），而非文件名，
    用户可从中选择某个字体文件，点击“确定”后返回该字体文件的完整路径。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择字体")
        self.resize(400, 600)

        # 列表控件
        self.list_widget = QListWidget()
        self.load_fonts()

        # 对话框按钮（确定 / 取消）
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def load_fonts(self):
        """
        扫描 C:/Windows/Fonts 文件夹中的 .ttf、.ttc、.otf 文件，
        使用 QFontDatabase 获取字体族名称，并将带有字体预览的项加入列表。
        """
        font_dir = r"C:\Windows\Fonts"
        exts = [".ttf", ".ttc", ".otf"]
        if os.path.exists(font_dir):
            for file in os.listdir(font_dir):
                lower_file = file.lower()
                if any(lower_file.endswith(ext) for ext in exts):
                    full_path = os.path.join(font_dir, file)
                    # 加载字体文件
                    font_id = QFontDatabase.addApplicationFont(full_path)
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        family = families[0]
                        # 使用字体族名称作为示例文字，同时展示预览效果
                        sample_text = f"{family} - 示例文字"
                        item_font = QFont(family, 14)
                    else:
                        # 若无法加载字体，则退化为显示文件名
                        sample_text = file
                        item_font = QFont()
                    item = QListWidgetItem(sample_text)
                    item.setFont(item_font)
                    # 将完整路径存储在 Item 的 UserRole 数据中
                    item.setData(Qt.UserRole, full_path)
                    self.list_widget.addItem(item)

    def get_selected_font_path(self):
        """
        返回用户选择的字体文件完整路径；若无选择则返回 None。
        """
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None
    
class WatermarkProcessor:
    """
    负责图像水印处理，将文本和图片水印应用到原图上。
    """
    def __init__(self, original_image, font_path):
        # original_image 为 cv2 格式（BGR），font_path 为字体路径
        self.original_image = original_image
        self.font_path = font_path

    def apply_text_watermark(self, image, text, font_size, position, opacity, offset_x, offset_y, 
                             shadow=False, shadow_width=0, shadow_intensity=50):
        """
        在传入的 PIL 图像上添加文本水印，返回叠加图层、文本位置及文本尺寸。
        如果 shadow 为 True，则在文字四周添加渐变阴影（只出现在文字外部），
        阴影模糊半径由 shadow_width 指定，阴影浓淡由 shadow_intensity 决定（百分比），
        阴影不会覆盖文字本身。
        """
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        font = ImageFont.truetype(self.font_path, font_size)
        draw = ImageDraw.Draw(overlay)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        positions = {
            "右下角": (image.width - text_width - offset_x, image.height - text_height - offset_y),
            "左下角": (offset_x, image.height - text_height - offset_y),
            "左上角": (offset_x, offset_y),
            "右上角": (image.width - text_width - offset_x, offset_y)
        }
        text_pos = positions.get(position, (image.width - text_width - offset_x, image.height - text_height - offset_y))
        
        if shadow and shadow_width > 0:
            # 创建文字mask（灰度图，白色区域为文字区域）
            mask = Image.new("L", image.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text(text_pos, text, font=font, fill=255)
            # 对mask进行高斯模糊
            blurred = mask.filter(ImageFilter.GaussianBlur(radius=shadow_width))
            # 得到仅在文字外部的阴影区域（将原始文字mask减去）
            shadow_mask = ImageChops.subtract(blurred, mask)
            # 使用用户设置的阴影浓淡（shadow_intensity 0~100）
            desired_shadow_alpha = int(opacity * shadow_intensity / 100)
            shadow_mask = shadow_mask.point(lambda p: p * (desired_shadow_alpha / 255.0))
            # 生成阴影层（填充黑色）
            shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            shadow_layer.putalpha(shadow_mask)
            # 将阴影层合成到底部
            overlay = Image.alpha_composite(overlay, shadow_layer)
        
        # 绘制正常文字（确保文字区域不被阴影覆盖）
        draw = ImageDraw.Draw(overlay)
        draw.text(text_pos, text, font=font, fill=(255, 255, 255, opacity))
        return overlay, text_pos, (text_width, text_height)

    def apply_image_watermark(self, overlay, watermark_image, text_position, text_size, image_params):
        # 1. 解析用户输入
        size_percent = image_params.get("size", 10)  # 1~100
        wm_opacity = int(image_params.get("opacity", 80)) * 255 // 100
        spacing = image_params.get("spacing", 5)
        watermark_pos = image_params.get("position", "上")

        # 2. 计算目标尺寸
        bg_width, bg_height = overlay.size
        short_side = min(bg_width, bg_height)

        # 让“水印的短边 = 背景图短边 * size_percent%”
        wm_short_side_target = short_side * (size_percent / 100.0)

        # 原始水印尺寸
        wm_original_w = watermark_image.width
        wm_original_h = watermark_image.height
        wm_original_short_side = min(wm_original_w, wm_original_h)

        # 缩放比
        scale = wm_short_side_target / float(wm_original_short_side)

        # 算出最终缩放后的宽高
        new_w = int(wm_original_w * scale)
        new_h = int(wm_original_h * scale)

        # 3. 进行缩放
        wm_resized = watermark_image.resize((new_w, new_h), Image.Resampling.LANCZOS).convert('RGBA')

        # 4. 调整水印透明度
        alpha = wm_resized.split()[3]
        alpha = Image.eval(alpha, lambda a: wm_opacity * a // 255)
        wm_resized.putalpha(alpha)
        wm_w, wm_h = wm_resized.size

        # 5. 计算粘贴位置(保持你原先的逻辑不变)
        text_x, text_y = text_position
        text_width, text_height = text_size

        wm_positions = {
            "下": (text_x + (text_width - wm_w) // 2, text_y + text_height + spacing),
            "上": (text_x + (text_width - wm_w) // 2, text_y - wm_h - spacing),
            "左": (text_x - wm_w - spacing, text_y + (text_height - wm_h) // 2),
            "右": (text_x + text_width + spacing, text_y + (text_height - wm_h) // 2)
        }
        wm_pos = wm_positions.get(watermark_pos, (text_x + (text_width - wm_w) // 2, text_y - wm_h - spacing))
        overlay.paste(wm_resized, wm_pos, wm_resized)
        return overlay


    def process(self, text, text_params, image_watermark=None, image_params=None):
        base_image = Image.fromarray(cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)).convert('RGBA')
        overlay = Image.new('RGBA', base_image.size, (255, 255, 255, 0))

        # 获取背景图大小
        bg_width, bg_height = base_image.size
        short_side = min(bg_width, bg_height)

        # --- 将字体大小从“百分比”转成“像素” ---
        # 用户输入的 text_params["font_size"] 为 1~100
        font_size_percent = text_params.get("font_size", 10)  # 默认10%
        font_size_px = int(short_side * (font_size_percent / 100.0))

        # 将换算后的 px 大小替换掉原本 text_params["font_size"]
        # 让后面的 apply_text_watermark 正常使用像素单位
        text_params_px = text_params.copy()
        text_params_px["font_size"] = font_size_px

        # 调用 apply_text_watermark
        text_overlay, text_pos, text_size = self.apply_text_watermark(
            base_image,
            text,
            text_params_px["font_size"],
            text_params_px.get("position", "右下角"),
            int(text_params_px.get("opacity", 50)) * 255 // 100,
            text_params_px.get("offset_x", 120),
            text_params_px.get("offset_y", 120),
            shadow=text_params_px.get("shadow", False),
            shadow_width=text_params_px.get("shadow_width", 0),
            shadow_intensity=text_params_px.get("shadow_intensity", 50)
        )
        overlay = Image.alpha_composite(overlay, text_overlay)

        # 如果有图片水印，则添加
        if image_watermark and image_params:
            overlay = self.apply_image_watermark(overlay, image_watermark, text_pos, text_size, image_params)

        final_image = Image.alpha_composite(base_image, overlay)
        return final_image


def get_chinese_font():
    """
    依次检查常见字体路径，返回存在的字体路径。
    """
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arial.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

class ExportDialog(QDialog):
    """
    自定义对话框，允许用户选择输出格式、输出路径和（针对 JPEG）压缩质量。
    """
    def __init__(self, default_output, parent=None):
        super().__init__(parent)
        self.setWindowTitle("输出图片设置")
        self.selected_format = "JPEG"
        self.output_path = default_output
        self.jpeg_quality = 95  # 默认高画质压缩

        # 输出格式选择
        format_label = QLabel("输出格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "PNG"])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)

        # 输出文件路径
        file_label = QLabel("输出文件:")
        self.file_line_edit = QLineEdit(default_output)
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_file)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_line_edit)
        file_layout.addWidget(browse_btn)

        # JPEG质量设置
        quality_label = QLabel("JPEG质量:")
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_spin.setEnabled(True)

        # 按钮区
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # 整体布局
        layout = QVBoxLayout()
        layout.addWidget(format_label)
        layout.addWidget(self.format_combo)
        layout.addWidget(file_label)
        layout.addLayout(file_layout)
        layout.addWidget(quality_label)
        layout.addWidget(self.quality_spin)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def on_format_changed(self, fmt):
        self.selected_format = fmt
        if fmt == "PNG":
            self.quality_spin.setEnabled(False)
            path = self.file_line_edit.text()
            base, _ = os.path.splitext(path)
            self.file_line_edit.setText(base + ".png")
        else:
            self.quality_spin.setEnabled(True)
            path = self.file_line_edit.text()
            base, _ = os.path.splitext(path)
            self.file_line_edit.setText(base + ".jpg")

    def browse_file(self):
        if self.selected_format == "JPEG":
            filter_str = "JPEG (*.jpg *.jpeg)"
        else:
            filter_str = "PNG (*.png)"
        path, _ = QFileDialog.getSaveFileName(self, "选择输出文件", self.file_line_edit.text(), filter_str)
        if path:
            self.file_line_edit.setText(path)

    def get_settings(self):
        return {
            "format": self.selected_format,
            "output_path": self.file_line_edit.text(),
            "quality": self.quality_spin.value()
        }

class WatermarkApp(QMainWindow):
    """
    界面类，负责采集用户输入并调用 WatermarkProcessor 处理图像，同时展示处理后的图像。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle('批量水印工具')
        self.setGeometry(100, 100, 1200, 800)
        self.image_paths = []
        self.original_image = None  # 存储 cv2 格式图像（BGR）
        self.watermark_image = None  # 存储 PIL 格式的水印图片（RGBA）
        self.font_path = get_chinese_font()
        self.processor = None  # 图片加载后初始化
        self.initUI()
    def batch_export_images(self):
        # 如果没有加载图片则直接返回
        if not self.image_paths:
            return

        # 弹出批量输出设置对话框
        dialog = BatchExportDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        settings = dialog.get_settings()
        out_folder = settings["output_folder"]
        if not out_folder:
            return  # 未选择输出文件夹

        fmt = settings["format"]
        quality = settings["quality"]

        # 从当前界面获取水印参数（以第一张图片的设置为准）
        text = self.text_input.text()
        text_params = {
            "font_size": int(self.font_size_input.text()),
            "position": self.position_combo.currentText(),
            "opacity": int(self.opacity_input.text()),
            "offset_x": int(self.offset_x_input.text()),
            "offset_y": int(self.offset_y_input.text()),
            "shadow": self.shadow_checkbox.isChecked(),
            "shadow_width": int(self.shadow_width_input.text() or "0"),
            "shadow_intensity": int(self.shadow_intensity_input.text() or "50")
        }
        image_params = {
            "position": self.watermark_position_combo.currentText(),
            "size": int(self.watermark_size_input.text()),
            "opacity": int(self.watermark_opacity_input.text()),
            "spacing": int(self.spacing_input.text())
        }

        # 批量处理每张图片
        for img_path in self.image_paths:
            pil_img = Image.open(img_path)
            original_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            processor = WatermarkProcessor(original_image, self.font_path)
            final_image = processor.process(
                text,
                text_params,
                image_watermark=self.watermark_image,
                image_params=image_params if self.watermark_image else None
            )

            # 保持原文件名，生成输出路径
            filename = os.path.basename(img_path)
            out_path = os.path.join(out_folder, filename)

            # 根据原文件扩展名和选定格式来保存
            _, ext = os.path.splitext(filename)
            ext_lower = ext.lower()
            if fmt == "JPEG" or ext_lower in [".jpg", ".jpeg"]:
                final_image.convert("RGB").save(out_path, "JPEG", quality=quality)
            else:
                final_image.save(out_path, "PNG")

        print(f"批量输出完成，共处理 {len(self.image_paths)} 张图片，输出到：{out_folder}")
        
    # 在 WatermarkApp 类的 initUI 方法中，添加“选择字体”按钮
    def initUI(self):
        main_layout = QHBoxLayout()
        control_layout = QVBoxLayout()
        control_container = QWidget()
        control_container.setLayout(control_layout)
        control_container.setFixedWidth(int(self.width() * 0.3))
        def add_labeled_input(label_text, input_widget, default_value=None):
            layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)
            layout.addWidget(label)
            if default_value is not None:
                input_widget.setText(default_value)
            layout.addWidget(input_widget)
            control_layout.addLayout(layout)

        self.load_btn = QPushButton('加载图片')
        self.load_btn.clicked.connect(self.load_images)
        control_layout.addWidget(self.load_btn)

        # 文本水印相关输入
        self.text_input = QLineEdit(self)
        self.text_input.setText("测试")
        self.text_input.textChanged.connect(self.update_watermark)
        add_labeled_input("水印文本", self.text_input)

        self.position_combo = QComboBox(self)
        self.position_combo.addItems(["右下角", "左下角", "左上角", "右上角"])
        self.position_combo.setCurrentText("右下角")
        self.position_combo.currentIndexChanged.connect(self.update_watermark)
        add_labeled_input("位置", self.position_combo)

        self.opacity_input = QLineEdit(self)
        self.opacity_input.setValidator(QIntValidator(0, 100))
        self.opacity_input.setText("50")
        self.opacity_input.textChanged.connect(self.update_watermark)
        add_labeled_input("透明度 (%)", self.opacity_input)

        self.font_size_input = QLineEdit(self)
        self.font_size_input.setValidator(QIntValidator(1, 100))  # 允许用户输入 1~100
        self.font_size_input.setText("10")                       # 默认值 10
        self.font_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("字体大小(占背景图短边%)", self.font_size_input, "10")
        
        # 新增“选择字体”按钮（位于文本水印相关控件下方）
        self.font_select_btn = QPushButton("选择字体")
        self.font_select_btn.clicked.connect(self.select_font)
        control_layout.addWidget(self.font_select_btn)

        self.offset_x_input = QLineEdit(self)
        self.offset_x_input.setValidator(QIntValidator(0, 1000))
        self.offset_x_input.setText("120")
        self.offset_x_input.textChanged.connect(self.update_watermark)
        add_labeled_input("水平偏移 (px)", self.offset_x_input)

        self.offset_y_input = QLineEdit(self)
        self.offset_y_input.setValidator(QIntValidator(0, 1000))
        self.offset_y_input.setText("120")
        self.offset_y_input.textChanged.connect(self.update_watermark)
        add_labeled_input("垂直偏移 (px)", self.offset_y_input)

        self.spacing_input = QLineEdit(self)
        self.spacing_input.setValidator(QIntValidator(0, 100))
        self.spacing_input.setText("5")
        self.spacing_input.textChanged.connect(self.update_watermark)
        add_labeled_input("文字和图片间隔 (px)", self.spacing_input)

        # 新增复选框：是否添加阴影
        self.shadow_checkbox = QCheckBox("添加阴影")
        self.shadow_checkbox.stateChanged.connect(self.update_watermark)
        control_layout.addWidget(self.shadow_checkbox)

        # 新增输入框：阴影宽度（高斯模糊半径）
        self.shadow_width_input = QLineEdit(self)
        self.shadow_width_input.setValidator(QIntValidator(0, 100))
        self.shadow_width_input.setText("5")
        self.shadow_width_input.textChanged.connect(self.update_watermark)
        add_labeled_input("阴影宽度 (px)", self.shadow_width_input)

        # 新增输入框：阴影浓淡 (%)，默认50%
        self.shadow_intensity_input = QLineEdit(self)
        self.shadow_intensity_input.setValidator(QIntValidator(0, 100))
        self.shadow_intensity_input.setText("50")
        self.shadow_intensity_input.textChanged.connect(self.update_watermark)
        add_labeled_input("阴影浓淡 (%)", self.shadow_intensity_input)

        # 图片水印相关输入（以下部分保持不变）
        self.load_watermark_btn = QPushButton('加载图片水印')
        self.load_watermark_btn.clicked.connect(self.load_watermark_image)
        control_layout.addWidget(self.load_watermark_btn)

        self.watermark_position_combo = QComboBox(self)
        self.watermark_position_combo.addItems(["下", "上", "左", "右"])
        self.watermark_position_combo.setCurrentText("上")
        self.watermark_position_combo.currentIndexChanged.connect(self.update_watermark)
        add_labeled_input("图片水印位置", self.watermark_position_combo)

        self.watermark_size_input = QLineEdit(self)
        self.watermark_size_input.setValidator(QIntValidator(1, 100))  # 允许用户输入 1~100
        self.watermark_size_input.setText("10")                        # 默认值 10
        self.watermark_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("图片水印大小(占背景图短边%)", self.watermark_size_input, "10")

        self.watermark_opacity_input = QLineEdit(self)
        self.watermark_opacity_input.setValidator(QIntValidator(0, 100))
        self.watermark_opacity_input.setText("80")
        self.watermark_opacity_input.textChanged.connect(self.update_watermark)
        add_labeled_input("图片水印透明度 (%)", self.watermark_opacity_input)

        # 输出图片按钮
        self.export_btn = QPushButton("输出图片")
        self.export_btn.clicked.connect(self.export_image)
        control_layout.addWidget(self.export_btn)

        # 新增“批量输出”按钮
        self.batch_export_btn = QPushButton("批量输出")
        self.batch_export_btn.clicked.connect(self.batch_export_images)
        control_layout.addWidget(self.batch_export_btn)

        # 图像显示区域设置（保持不变）
        self.graphics_view = QGraphicsView(self)
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.image_item = QGraphicsPixmapItem()
        self.graphics_scene.addItem(self.image_item)

        main_layout.addWidget(control_container)
        main_layout.addWidget(self.graphics_view, 4)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.graphics_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def select_font(self):
        dialog = FontListDialog(self)  # 创建并弹出自定义对话框
        if dialog.exec_() == QDialog.Accepted:
            selected_font_path = dialog.get_selected_font_path()
            if selected_font_path:
                self.font_path = selected_font_path
                # 更新 WatermarkProcessor 中的字体路径
                if self.processor:
                    self.processor.font_path = self.font_path
                self.update_watermark()



    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 0.8
        self.graphics_view.scale(factor, factor)
        event.accept()

    def load_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if files:
            self.image_paths = files
            self.load_image(files[0])

    def load_image(self, path):
        if os.path.exists(path):
            image = Image.open(path)
            self.original_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            self.processor = WatermarkProcessor(self.original_image, self.font_path)
            self.update_watermark()
            self.fit_image_to_view()

    def load_watermark_image(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择水印图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file:
            self.watermark_image = Image.open(file).convert('RGBA')
            self.update_watermark()

    def fit_image_to_view(self):
        if self.original_image is not None:
            self.graphics_view.fitInView(self.image_item, Qt.KeepAspectRatio)

    def show_image(self, pil_image):
        if pil_image is not None:
            image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2RGB)
            h, w, ch = image.shape
            bytes_per_line = ch * w
            q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            self.image_item.setPixmap(pixmap)
            self.graphics_scene.setSceneRect(0, 0, w, h)

    def update_watermark(self):
        if self.original_image is None or not self.processor:
            return
        text = self.text_input.text()
        text_params = {
            "font_size": int(self.font_size_input.text()),
            "position": self.position_combo.currentText(),
            "opacity": int(self.opacity_input.text()),
            "offset_x": int(self.offset_x_input.text()),
            "offset_y": int(self.offset_y_input.text()),
            "shadow": self.shadow_checkbox.isChecked(),
            "shadow_width": int(self.shadow_width_input.text() or "0"),
            "shadow_intensity": int(self.shadow_intensity_input.text() or "50")
        }
        image_params = {
            "position": self.watermark_position_combo.currentText(),
            "size": int(self.watermark_size_input.text()),
            "opacity": int(self.watermark_opacity_input.text()),
            "spacing": int(self.spacing_input.text())
        }
        final_image = self.processor.process(
            text,
            text_params,
            image_watermark=self.watermark_image,
            image_params=image_params if self.watermark_image else None
        )
        self.show_image(final_image)

    def export_image(self):
        if self.original_image is None or not self.processor:
            return

        default_output = "example_waterMarked.jpg"
        if self.image_paths:
            base_name = os.path.basename(self.image_paths[0])
            name, ext = os.path.splitext(base_name)
            default_output = os.path.join(os.path.dirname(self.image_paths[0]), name + "_waterMarked" + ext)
        dialog = ExportDialog(default_output, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            fmt = settings["format"]
            output_path = settings["output_path"]
            quality = settings["quality"]

            text = self.text_input.text()
            text_params = {
                "font_size": int(self.font_size_input.text()),
                "position": self.position_combo.currentText(),
                "opacity": int(self.opacity_input.text()),
                "offset_x": int(self.offset_x_input.text()),
                "offset_y": int(self.offset_y_input.text()),
                "shadow": self.shadow_checkbox.isChecked(),
                "shadow_width": int(self.shadow_width_input.text()),
                "shadow_intensity": int(self.shadow_intensity_input.text() or "50")
            }
            image_params = {
                "position": self.watermark_position_combo.currentText(),
                "size": int(self.watermark_size_input.text()),
                "opacity": int(self.watermark_opacity_input.text()),
                "spacing": int(self.spacing_input.text())
            }
            final_image = self.processor.process(
                text,
                text_params,
                image_watermark=self.watermark_image,
                image_params=image_params if self.watermark_image else None
            )

            try:
                if fmt == "JPEG":
                    final_image.convert('RGB').save(output_path, "JPEG", quality=quality)
                else:
                    final_image.save(output_path, "PNG")
            except Exception as e:
                print("保存失败:", e)
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WatermarkApp()
    window.show()
    sys.exit(app.exec_())
