import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QDialog,
                             QDialogButtonBox, QSpinBox, QCheckBox)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QIntValidator
from PyQt5.QtCore import Qt

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
        """
        在叠加图层上添加图片水印，水印相对于文本水印的位置进行定位。
        """
        wm_scale = image_params.get("size", 40) / 100.0
        wm_opacity = int(image_params.get("opacity", 80)) * 255 // 100
        spacing = image_params.get("spacing", 5)
        watermark_pos = image_params.get("position", "上")

        wm_resized = watermark_image.resize(
            (int(watermark_image.width * wm_scale), int(watermark_image.height * wm_scale)),
            Image.Resampling.LANCZOS
        ).convert('RGBA')

        # 调整水印透明度
        alpha = wm_resized.split()[3]
        alpha = Image.eval(alpha, lambda a: wm_opacity * a // 255)
        wm_resized.putalpha(alpha)
        wm_w, wm_h = wm_resized.size

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
        """
        根据传入的参数在原图上添加文本和（可选的）图片水印，
        返回处理后的 PIL 图像。
        """
        base_image = Image.fromarray(cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)).convert('RGBA')
        overlay = Image.new('RGBA', base_image.size, (255, 255, 255, 0))
        # 文本水印参数（opacity由百分比转换为0-255）
        text_overlay, text_pos, text_size = self.apply_text_watermark(
            base_image,
            text,
            text_params.get("font_size", 220),
            text_params.get("position", "右下角"),
            int(text_params.get("opacity", 50)) * 255 // 100,
            text_params.get("offset_x", 120),
            text_params.get("offset_y", 120),
            shadow=text_params.get("shadow", False),
            shadow_width=text_params.get("shadow_width", 0),
            shadow_intensity=text_params.get("shadow_intensity", 50)
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
        self.font_size_input.setValidator(QIntValidator(10, 500))
        self.font_size_input.setText("220")
        self.font_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("字体大小", self.font_size_input)

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

        # 图片水印相关输入
        self.load_watermark_btn = QPushButton('加载图片水印')
        self.load_watermark_btn.clicked.connect(self.load_watermark_image)
        control_layout.addWidget(self.load_watermark_btn)

        self.watermark_position_combo = QComboBox(self)
        self.watermark_position_combo.addItems(["下", "上", "左", "右"])
        self.watermark_position_combo.setCurrentText("上")
        self.watermark_position_combo.currentIndexChanged.connect(self.update_watermark)
        add_labeled_input("图片水印位置", self.watermark_position_combo)

        self.watermark_size_input = QLineEdit(self)
        self.watermark_size_input.setValidator(QIntValidator(10, 200))
        self.watermark_size_input.setText("40")
        self.watermark_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("图片水印大小 (%)", self.watermark_size_input)

        self.watermark_opacity_input = QLineEdit(self)
        self.watermark_opacity_input.setValidator(QIntValidator(0, 100))
        self.watermark_opacity_input.setText("80")
        self.watermark_opacity_input.textChanged.connect(self.update_watermark)
        add_labeled_input("图片水印透明度 (%)", self.watermark_opacity_input)

        # 输出图片按钮
        self.export_btn = QPushButton("输出图片")
        self.export_btn.clicked.connect(self.export_image)
        control_layout.addWidget(self.export_btn)

        # 图像显示区域
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
