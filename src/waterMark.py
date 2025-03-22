import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSlider)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QIntValidator
from PyQt5.QtCore import Qt

class WatermarkApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('批量水印工具')
        self.setGeometry(100, 100, 1200, 800)
        self.image_paths = []
        self.current_image = None
        self.original_image = None
        self.watermark_image = None
        self.font_path = self.get_chinese_font()
        self.initUI()

    def get_chinese_font(self):
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/arial.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return path
        return None

    def initUI(self):
        main_layout = QHBoxLayout()

        control_layout = QVBoxLayout()
        control_container = QWidget()
        control_container.setLayout(control_layout)
        control_container.setFixedWidth(int(self.width() * 0.3))

        # 通用方法创建标签 + 输入框布局
        def add_labeled_input(label_text, input_widget, default_value=None):
            layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)  # 统一设置宽度
            layout.addWidget(label)

            if default_value is not None:
                input_widget.setText(default_value)
            layout.addWidget(input_widget)
            control_layout.addLayout(layout)

        # 加载图片按钮
        self.load_btn = QPushButton('加载图片')
        self.load_btn.clicked.connect(self.load_images)
        control_layout.addWidget(self.load_btn)

        # 文本输入（初始值为"测试"）
        self.text_input = QLineEdit(self)
        self.text_input.setText("测试")
        self.text_input.textChanged.connect(self.update_watermark)
        add_labeled_input("水印文本", self.text_input)

        # 位置（初始值为"右下角"）
        self.position_combo = QComboBox(self)
        self.position_combo.addItems(["右下角", "左下角", "左上角", "右上角"])
        self.position_combo.setCurrentText("右下角")
        self.position_combo.currentIndexChanged.connect(self.update_watermark)
        add_labeled_input("位置", self.position_combo)

        # 透明度（初始值为50）
        self.opacity_input = QLineEdit(self)
        self.opacity_input.setValidator(QIntValidator(0, 100))
        self.opacity_input.setText("50")
        self.opacity_input.textChanged.connect(self.update_watermark)
        add_labeled_input("透明度 (%)", self.opacity_input)

        # 字体大小（初始值为220）
        self.font_size_input = QLineEdit(self)
        self.font_size_input.setValidator(QIntValidator(10, 500))
        self.font_size_input.setText("220")
        self.font_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("字体大小", self.font_size_input)

        # 水平偏移（初始值为120）
        self.offset_x_input = QLineEdit(self)
        self.offset_x_input.setValidator(QIntValidator(0, 1000))
        self.offset_x_input.setText("120")
        self.offset_x_input.textChanged.connect(self.update_watermark)
        add_labeled_input("水平偏移 (px)", self.offset_x_input)

        # 垂直偏移（初始值为120）
        self.offset_y_input = QLineEdit(self)
        self.offset_y_input.setValidator(QIntValidator(0, 1000))
        self.offset_y_input.setText("120")
        self.offset_y_input.textChanged.connect(self.update_watermark)
        add_labeled_input("垂直偏移 (px)", self.offset_y_input)

        # 文字和图片间隔（初始值为5）
        self.spacing_input = QLineEdit(self)
        self.spacing_input.setValidator(QIntValidator(0, 100))
        self.spacing_input.setText("5")
        self.spacing_input.textChanged.connect(self.update_watermark)
        add_labeled_input("文字和图片间隔 (px)", self.spacing_input)

        # 加载图片水印按钮
        self.load_watermark_btn = QPushButton('加载图片水印')
        self.load_watermark_btn.clicked.connect(self.load_watermark_image)
        control_layout.addWidget(self.load_watermark_btn)

        # 图片水印位置（初始值为"上"）
        self.watermark_position_combo = QComboBox(self)
        self.watermark_position_combo.addItems(["下", "上", "左", "右"])
        self.watermark_position_combo.setCurrentText("上")
        self.watermark_position_combo.currentIndexChanged.connect(self.update_watermark)
        add_labeled_input("图片水印位置", self.watermark_position_combo)

        # 图片水印大小（初始值为40%）
        self.watermark_size_input = QLineEdit(self)
        self.watermark_size_input.setValidator(QIntValidator(10, 200))
        self.watermark_size_input.setText("40")
        self.watermark_size_input.textChanged.connect(self.update_watermark)
        add_labeled_input("图片水印大小 (%)", self.watermark_size_input)

        # 图片水印透明度（初始值为80%）
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

        # 主要布局
        main_layout.addWidget(control_container)
        main_layout.addWidget(self.graphics_view, 4)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # 显示设置
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
            self.current_image = self.original_image.copy()
            self.update_watermark()
            self.fit_image_to_view()

    def load_watermark_image(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择水印图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file:
            self.watermark_image = Image.open(file).convert('RGBA')
            self.update_watermark()

    def fit_image_to_view(self):
        if self.current_image is not None:
            self.graphics_view.fitInView(self.image_item, Qt.KeepAspectRatio)

    def show_image(self):
        if self.current_image is not None:
            image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            h, w, ch = image.shape
            bytes_per_line = ch * w
            q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            self.image_item.setPixmap(pixmap)
            self.graphics_scene.setSceneRect(0, 0, w, h)
    def update_watermark(self):
        if self.original_image is None:
            return

        self.current_image = self.original_image.copy()
        image = Image.fromarray(cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB))
        overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        font = ImageFont.truetype(self.font_path, int(self.font_size_input.text()))
        text = self.text_input.text()
        text_position = self.position_combo.currentText()
        opacity = int(self.opacity_input.text()) * 255 // 100
        
        # 计算文本宽度和高度
        bbox = draw.textbbox((0, 0), text, font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        offset_x = int(self.offset_x_input.text())
        offset_y = int(self.offset_y_input.text())

        # 设置文字水印的位置
        positions = {
            "右下角": (image.width - text_width - offset_x, image.height - text_height - offset_y),
            "左下角": (offset_x, image.height - text_height - offset_y),
            "左上角": (offset_x, offset_y),
            "右上角": (image.width - text_width - offset_x, offset_y)
        }

        text_pos = positions[text_position]
        
        # 绘制文字水印
        draw.text(text_pos, text, font=font, fill=(255, 255, 255, opacity))

        # 如果加载了图片水印
        if self.watermark_image:
            watermark_pos = self.watermark_position_combo.currentText()
            wm_scale = int(self.watermark_size_input.text()) / 100
            wm_opacity = int(self.watermark_opacity_input.text()) * 255 // 100

            # 调整水印大小
            wm_resized = self.watermark_image.resize(
                (int(self.watermark_image.width * wm_scale), int(self.watermark_image.height * wm_scale)),
                Image.Resampling.LANCZOS
            ).convert('RGBA')

            alpha = wm_resized.split()[3]
            alpha = Image.eval(alpha, lambda a: wm_opacity * a // 255)
            wm_resized.putalpha(alpha)

            wm_w, wm_h = wm_resized.size

            # ✅ 读取用户设置的间隔
            spacing = int(self.spacing_input.text())

            # ✅ 根据位置动态设置水印位置
            wm_positions = {
                "下": (text_pos[0] + (text_width - wm_w) // 2, text_pos[1] + text_height + spacing),
                "上": (text_pos[0] + (text_width - wm_w) // 2, text_pos[1] - wm_h - spacing),
                "左": (text_pos[0] - wm_w - spacing, text_pos[1] + (text_height - wm_h) // 2),
                "右": (text_pos[0] + text_width + spacing, text_pos[1] + (text_height - wm_h) // 2)
            }

            wm_x, wm_y = wm_positions[watermark_pos]

            # ✅ 粘贴图片水印
            overlay.paste(wm_resized, (wm_x, wm_y), wm_resized)

        # 合成图片和水印
        self.current_image = cv2.cvtColor(
            np.array(Image.alpha_composite(image.convert('RGBA'), overlay)),
            cv2.COLOR_RGBA2BGR
        )
        self.show_image()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WatermarkApp()
    window.show()
    sys.exit(app.exec_())