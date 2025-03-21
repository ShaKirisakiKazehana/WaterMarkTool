import javafx.application.Application;
import javafx.stage.Stage;
import javafx.stage.FileChooser;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.*;
import javafx.scene.control.*;
import javafx.scene.paint.Color;
import javafx.scene.canvas.Canvas;
import javafx.scene.canvas.GraphicsContext;

import javax.imageio.ImageIO;
import java.io.File;
import java.awt.image.BufferedImage;
import java.awt.AlphaComposite;
import java.awt.Graphics2D;
import java.awt.Font;
import java.awt.Color as AwtColor;
import java.util.List;

public class WatermarkApp extends Application {

    private List<File> imageFiles;
    private File watermarkImageFile;
    private String watermarkText = "My Watermark";
    private double watermarkScale = 1.0;
    private double watermarkOpacity = 0.5;
    private String position = "bottom-right";
    
    private ImageView previewImageView;
    private BufferedImage previewBufferedImage;
    private Canvas previewCanvas;

    @Override
    public void start(Stage primaryStage) {
        BorderPane root = new BorderPane();

        // ================== 左侧控制面板 ==================
        VBox controlPanel = new VBox(10);
        controlPanel.setPrefWidth(300);
        controlPanel.setStyle("-fx-background-color: #f0f0f0; -fx-padding: 15;");

        // 1. 批量导入图片按钮
        Button importButton = new Button("Import Images");
        importButton.setOnAction(e -> loadImages());

        // 2. 添加文字水印
        TextField textField = new TextField(watermarkText);
        textField.setPromptText("Watermark Text");
        textField.setOnAction(e -> {
            watermarkText = textField.getText();
            updatePreview();
        });

        // 3. 添加图片水印
        Button imageWatermarkButton = new Button("Import Watermark Image");
        imageWatermarkButton.setOnAction(e -> loadWatermarkImage());

        // 4. 水印位置
        ChoiceBox<String> positionChoiceBox = new ChoiceBox<>();
        positionChoiceBox.getItems().addAll("top-left", "top-right", "bottom-left", "bottom-right", "custom");
        positionChoiceBox.setValue(position);
        positionChoiceBox.setOnAction(e -> {
            position = positionChoiceBox.getValue();
            updatePreview();
        });

        // 5. 水印缩放滑块
        Slider scaleSlider = new Slider(0.1, 3.0, watermarkScale);
        scaleSlider.setShowTickLabels(true);
        scaleSlider.setShowTickMarks(true);
        scaleSlider.setMajorTickUnit(0.5);
        scaleSlider.valueProperty().addListener((obs, oldVal, newVal) -> {
            watermarkScale = newVal.doubleValue();
            updatePreview();
        });

        // 6. 水印透明度滑块
        Slider opacitySlider = new Slider(0.0, 1.0, watermarkOpacity);
        opacitySlider.setShowTickLabels(true);
        opacitySlider.setShowTickMarks(true);
        opacitySlider.setMajorTickUnit(0.1);
        opacitySlider.valueProperty().addListener((obs, oldVal, newVal) -> {
            watermarkOpacity = newVal.doubleValue();
            updatePreview();
        });

        // 7. 导出按钮
        Button exportButton = new Button("Export Images");
        exportButton.setOnAction(e -> exportImages());

        // 添加控件到控制面板
        controlPanel.getChildren().addAll(
                importButton,
                textField,
                imageWatermarkButton,
                positionChoiceBox,
                new Label("Scale:"),
                scaleSlider,
                new Label("Opacity:"),
                opacitySlider,
                exportButton
        );

        // ================== 右侧预览窗口 ==================
        previewCanvas = new Canvas(600, 600);
        StackPane previewPane = new StackPane(previewCanvas);
        previewPane.setStyle("-fx-background-color: #ddd;");

        // 设置主窗口布局
        root.setLeft(controlPanel);
        root.setCenter(previewPane);

        Scene scene = new Scene(root, 1000, 800);
        primaryStage.setTitle("Watermark Tool");
        primaryStage.setScene(scene);
        primaryStage.show();
    }

    // ================== 导入图片 ==================
    private void loadImages() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("Image Files", "*.png", "*.jpg", "*.jpeg"));
        imageFiles = fileChooser.showOpenMultipleDialog(null);
        if (imageFiles != null && !imageFiles.isEmpty()) {
            loadPreviewImage(imageFiles.get(0));
        }
    }

    // ================== 加载预览 ==================
    private void loadPreviewImage(File file) {
        try {
            previewBufferedImage = ImageIO.read(file);
            updatePreview();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // ================== 加载水印图片 ==================
    private void loadWatermarkImage() {
        FileChooser fileChooser = new FileChooser();
        watermarkImageFile = fileChooser.showOpenDialog(null);
        updatePreview();
    }

    // ================== 更新预览 ==================
    private void updatePreview() {
        if (previewBufferedImage == null) return;

        GraphicsContext gc = previewCanvas.getGraphicsContext2D();
        gc.clearRect(0, 0, previewCanvas.getWidth(), previewCanvas.getHeight());

        // 绘制预览图像
        gc.drawImage(new Image(previewBufferedImage.toURI().toString()), 0, 0, 600, 600);

        // 绘制文字水印
        gc.setFill(Color.rgb(255, 255, 255, (int) (255 * watermarkOpacity)));
        gc.setFont(javafx.scene.text.Font.font(20 * watermarkScale));
        gc.fillText(watermarkText, 20, 40);
    }

    // ================== 导出图片 ==================
    private void exportImages() {
        System.out.println("Exporting...");
    }

    public static void main(String[] args) {
        launch(args);
    }
}
