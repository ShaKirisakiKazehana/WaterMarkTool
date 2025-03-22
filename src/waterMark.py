import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem)
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

    def apply_text_watermark(self, image, text, font_size, position, opacity, offset_x, offset_y):
        """
        在传入的 PIL 图像上添加文本水印，返回叠加图层、文本位置及文本尺寸。
        """
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        font = ImageFont.truetype(self.font_path, font_size)
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
        # 文本水印参数
        text_overlay, text_pos, text_size = self.apply_text_watermark(
            base_image,
            text,
            text_params.get("font_size", 220),
            text_params.get("position", "右下角"),
            int(text_params.get("opacity", 50)) * 255 // 100,
            text_params.get("offset_x", 120),
            text_params.get("offset_y", 120)
        )
        overlay = Image.alpha_composite(overlay, text_overlay)
        # 图片水印（如果存在）
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

class WatermarkApp(QMainWindow):
    """
    界面类，负责采集用户输入并调用 WatermarkProcessor 处理图像，
    同时展示处理后的图像。
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

        # 辅助函数，用于生成标签和输入框组合
        def add_labeled_input(label_text, input_widget, default_value=None):
            layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)
            layout.addWidget(label)
            if default_value is not None:
                input_widget.setText(default_value)
            layout.addWidget(input_widget)
            control_layout.addLayout(layout)

        # 加载图片按钮
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

        # 图像预览设置
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
            # 将 PIL 图像转换为 OpenCV BGR 格式
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
            # 将 PIL 图像转换为 QPixmap 显示
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
        # 收集文本水印参数
        text = self.text_input.text()
        text_params = {
            "font_size": int(self.font_size_input.text()),
            "position": self.position_combo.currentText(),
            "opacity": int(self.opacity_input.text()),
            "offset_x": int(self.offset_x_input.text()),
            "offset_y": int(self.offset_y_input.text())
        }
        # 收集图片水印参数
        image_params = {
            "position": self.watermark_position_combo.currentText(),
            "size": int(self.watermark_size_input.text()),
            "opacity": int(self.watermark_opacity_input.text()),
            "spacing": int(self.spacing_input.text())
        }
        # 调用处理逻辑，获取水印处理后的图像
        final_image = self.processor.process(
            text,
            text_params,
            image_watermark=self.watermark_image,
            image_params=image_params if self.watermark_image else None
        )
        self.show_image(final_image)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WatermarkApp()
    window.show()
    sys.exit(app.exec_())
