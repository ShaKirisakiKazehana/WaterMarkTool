import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFont, ImageTk

class WatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批量添加水印工具")
        self.root.geometry("500x400")

        self.input_folder = ""
        self.output_folder = ""
        self.watermark_text = ""
        self.watermark_image = None
        self.position = "bottom_right"
        self.transparency = 0.5
        self.rotation = 0
        self.font_size = 36
        self.font_path = "arial.ttf"
        self.margin = 10

        self.create_widgets()

    def create_widgets(self):
        # 选择输入文件夹
        tk.Button(self.root, text="选择输入文件夹", command=self.select_input_folder).pack(pady=5)
        tk.Button(self.root, text="选择输出文件夹", command=self.select_output_folder).pack(pady=5)

        # 选择水印（文本或图片）
        tk.Button(self.root, text="设置文字水印", command=self.set_text_watermark).pack(pady=5)
        tk.Button(self.root, text="选择图片水印", command=self.set_image_watermark).pack(pady=5)

        # 位置选择
        positions = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
        self.position_var = tk.StringVar(value=self.position)
        tk.Label(self.root, text="水印位置：").pack()
        tk.OptionMenu(self.root, self.position_var, *positions).pack()

        # 透明度滑块
        tk.Label(self.root, text="透明度：").pack()
        self.transparency_slider = tk.Scale(self.root, from_=0, to=1, resolution=0.05, orient="horizontal")
        self.transparency_slider.set(self.transparency)
        self.transparency_slider.pack()

        # 旋转角度滑块
        tk.Label(self.root, text="旋转角度：").pack()
        self.rotation_slider = tk.Scale(self.root, from_=0, to=360, orient="horizontal")
        self.rotation_slider.set(self.rotation)
        self.rotation_slider.pack()

        # 批量处理按钮
        tk.Button(self.root, text="开始处理", command=self.process_images).pack(pady=10)

    def select_input_folder(self):
        self.input_folder = filedialog.askdirectory()
        if not self.input_folder:
            messagebox.showerror("错误", "未选择输入文件夹")

    def select_output_folder(self):
        self.output_folder = filedialog.askdirectory()
        if not self.output_folder:
            messagebox.showerror("错误", "未选择输出文件夹")

    def set_text_watermark(self):
        self.watermark_text = simpledialog.askstring("输入文字水印", "请输入水印内容：")

    def set_image_watermark(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if file_path:
            self.watermark_image = Image.open(file_path)

    def add_watermark(self, img):
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))

        if self.watermark_image:
            mark = self.watermark_image.convert("RGBA")
            mark = mark.resize((int(img.width * 0.2), int(img.height * 0.2)), Image.ANTIALIAS)
        else:
            font = ImageFont.truetype(self.font_path, self.font_size)
            mark = Image.new('RGBA', font.getsize(self.watermark_text), (0, 0, 0, 0))
            draw = ImageDraw.Draw(mark)
            draw.text((0, 0), self.watermark_text, font=font, fill=(255, 255, 255, int(255 * self.transparency)))

        # 旋转水印
        mark = mark.rotate(self.rotation, expand=True)

        # 确定位置
        if self.position_var.get() == 'top_left':
            position = (self.margin, self.margin)
        elif self.position_var.get() == 'top_right':
            position = (img.width - mark.width - self.margin, self.margin)
        elif self.position_var.get() == 'bottom_left':
            position = (self.margin, img.height - mark.height - self.margin)
        elif self.position_var.get() == 'bottom_right':
            position = (img.width - mark.width - self.margin, img.height - mark.height - self.margin)
        else:
            position = ((img.width - mark.width) // 2, (img.height - mark.height) // 2)

        # 叠加水印
        watermark.paste(mark, position, mark)

        # 合并图层
        watermarked = Image.alpha_composite(img.convert("RGBA"), watermark)

        return watermarked.convert("RGB")

    def process_images(self):
        if not self.input_folder or not self.output_folder:
            messagebox.showerror("错误", "请先选择输入和输出文件夹")
            return

        files = [f for f in os.listdir(self.input_folder) if f.lower().endswith(('png', 'jpg', 'jpeg', 'bmp'))]
        if not files:
            messagebox.showerror("错误", "输入文件夹中没有可处理的图片")
            return

        for file in files:
            input_path = os.path.join(self.input_folder, file)
            output_path = os.path.join(self.output_folder, file)

            img = Image.open(input_path).convert("RGBA")
            watermarked = self.add_watermark(img)
            watermarked.save(output_path, quality=95)

        messagebox.showinfo("完成", f"已成功处理 {len(files)} 张图片！")

if __name__ == "__main__":
    root = tk.Tk()
    app = WatermarkApp(root)
    root.mainloop()
