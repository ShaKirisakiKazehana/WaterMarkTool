import sys
import os
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem)
from PyQt5.QtGui import QPixmap, QImage, QMouseEvent, QPainter, QFontDatabase, QIntValidator
from PyQt5.QtCore import Qt, QPointF
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

class WatermarkApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('批量水印工具')
        self.setGeometry(100, 100, 1200, 800)
        self.image_paths = []
        self.current_image = None
        self.original_image = None
        self.watermark_text = "示例水印"
        self.watermark_position = "右下角"
        self.opacity = 128
        self.scale_factor = 1.0
        self.font_size = 40
        self.dragging = False
        self.last_mouse_position = QPointF()

        # 加载系统字体路径
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
                print(f"找到字体: {path}")
                return path

        print("未找到中文字体，使用默认字体")
        return None

    def initUI(self):
        main_layout = QHBoxLayout()

        # 控制区（左侧） - 占20%
        control_layout = QVBoxLayout()
        control_container = QWidget()
        control_container.setLayout(control_layout)
        control_container.setFixedWidth(int(self.width() * 0.2))

        # 加载图片按钮
        self.load_btn = QPushButton('加载图片')
        self.load_btn.clicked.connect(self.load_images)
        control_layout.addWidget(self.load_btn)

        # 文本水印输入
        self.text_input = QLineEdit(self)
        self.text_input.setPlaceholderText("输入水印文本")
        self.text_input.textChanged.connect(lambda: self.update_watermark())
        control_layout.addWidget(self.text_input)

        # 位置下拉框
        self.position_combo = QComboBox(self)
        self.position_combo.addItems(["左上角", "右上角", "左下角", "右下角"])
        self.position_combo.currentIndexChanged.connect(lambda: self.update_watermark())
        control_layout.addWidget(self.position_combo)

        # 透明度输入框及标签
        self.opacity_label = QLabel("透明度 (%)")
        control_layout.addWidget(self.opacity_label)
        self.opacity_input = QLineEdit(self)
        self.opacity_input.setText("50")
        self.opacity_input.setValidator(QIntValidator(0, 100))
        self.opacity_input.textChanged.connect(lambda: self.update_watermark())
        control_layout.addWidget(self.opacity_input)

        # 字体大小输入框及标签
        self.font_size_label = QLabel("字体大小")
        control_layout.addWidget(self.font_size_label)
        self.font_size_input = QLineEdit(self)
        self.font_size_input.setText("40")
        self.font_size_input.setValidator(QIntValidator(10, 100))
        self.font_size_input.textChanged.connect(lambda: self.update_watermark())
        control_layout.addWidget(self.font_size_input)

        # 预览区（右侧） - 占80%
        self.graphics_view = QGraphicsView(self)
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.image_item = QGraphicsPixmapItem()
        self.graphics_scene.addItem(self.image_item)

        main_layout.addWidget(control_container)
        main_layout.addWidget(self.graphics_view, 4) # 设置比例 1:4（20% : 80%）

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)

        # 添加缩放功能
        self.graphics_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.graphics_view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 0.8
        self.graphics_view.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse_position = event.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.pos() - self.last_mouse_position
            self.graphics_view.horizontalScrollBar().setValue(
                self.graphics_view.horizontalScrollBar().value() - delta.x())
            self.graphics_view.verticalScrollBar().setValue(
                self.graphics_view.verticalScrollBar().value() - delta.y())
            self.last_mouse_position = event.pos()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    def load_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if files:
            self.image_paths = files
            self.load_image(files[0])

    def load_image(self, path):
        path = os.path.normpath(path)
        if os.path.exists(path):
            image = Image.open(path)
            self.original_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            self.current_image = self.original_image.copy()
            self.update_watermark()
            # 自适应窗口大小
            self.fit_image_to_view()

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
        if self.original_image is not None:
            self.current_image = self.original_image.copy()

            text = self.text_input.text()
            position = self.position_combo.currentText()
            opacity = int(self.opacity_input.text()) * 255 // 100
            font_size = int(self.font_size_input.text())

            image = Image.fromarray(cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB))
            overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            font = ImageFont.truetype(self.font_path, font_size)

            bbox = draw.textbbox((0, 0), text, font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            pos = {
                "左上角": (10, 10),
                "右上角": (image.width - text_width - 10, 10),
                "左下角": (10, image.height - text_height - 10),
                "右下角": (image.width - text_width - 10, image.height - text_height - 10)
            }[position]

            draw.text(pos, text, font=font, fill=(255, 255, 255, opacity))
            self.current_image = cv2.cvtColor(np.array(Image.alpha_composite(image.convert('RGBA'), overlay)), cv2.COLOR_RGBA2BGR)
            self.show_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WatermarkApp()
    window.show()
    sys.exit(app.exec_())