package com.example.anygrow;

import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.scene.Node;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart;
import javafx.scene.control.Label;
import javafx.scene.layout.*;
import javafx.scene.text.Font;

public class SensorChartsPane extends GridPane {

    private final XYChart.Series<Number, Number> tempSeries = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> humSeries  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> co2Series  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> illSeries  = new XYChart.Series<>();

    private int sampleIndex = 0;

    public SensorChartsPane() {
        setHgap(10);
        setVgap(10);
        setPadding(new Insets(6));

        // 각 센서별 차트 생성
        LineChart<Number, Number> tempChart =
                createChart("시간 흐름", "온도 (℃)", 0, 50, 10, tempSeries);
        LineChart<Number, Number> humChart =
                createChart("시간 흐름", "습도 (%)", 0, 100, 20, humSeries);
        LineChart<Number, Number> co2Chart =
                createChart("시간 흐름", "CO₂ (ppm)", 0, 6000, 1000, co2Series);
        LineChart<Number, Number> illChart =
                createChart("시간 흐름", "조도 (lx)", 0, 2000, 500, illSeries);

        // 2x2 배치 + 테두리 타이틀
        add(wrapWithBorderTitle("온도 그래프", tempChart), 0, 0);
        add(wrapWithBorderTitle("습도 그래프", humChart), 1, 0);
        add(wrapWithBorderTitle("CO₂ 그래프", co2Chart), 0, 1);
        add(wrapWithBorderTitle("조도 그래프", illChart), 1, 1);

        // GridPane 셀 확장 설정
        for (Node n : getChildren()) {
            GridPane.setHgrow(n, Priority.ALWAYS);
            GridPane.setVgrow(n, Priority.ALWAYS);
        }
    }

    /**
     * 센서 데이터 1회 갱신 시 호출
     */
    public void addPoint(double temp, double hum, double co2, double ill) {
        int x = sampleIndex++;

        tempSeries.getData().add(new XYChart.Data<>(x, temp));
        humSeries.getData().add(new XYChart.Data<>(x, hum));
        co2Series.getData().add(new XYChart.Data<>(x, co2));
        illSeries.getData().add(new XYChart.Data<>(x, ill));

        trim(tempSeries, 200);
        trim(humSeries, 200);
        trim(co2Series, 200);
        trim(illSeries, 200);
    }

    // -----------------------------
    // 내부 유틸
    // -----------------------------
    private void trim(XYChart.Series<Number, Number> s, int max) {
        if (s.getData().size() > max) {
            s.getData().remove(0, s.getData().size() - max);
        }
    }

    private LineChart<Number, Number> createChart(
            String xLabel,
            String yLabel,
            double minY,
            double maxY,
            double tickY,
            XYChart.Series<Number, Number> series
    ) {
        NumberAxis xAxis = new NumberAxis();
        xAxis.setLabel(xLabel);

        NumberAxis yAxis = new NumberAxis(minY, maxY, tickY);
        yAxis.setLabel(yLabel);

        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setCreateSymbols(false);
        chart.setAnimated(false);
        chart.setLegendVisible(false);
        chart.setMinHeight(160);

        chart.getData().add(series);

        // 그래프 선 두께 조절 (Scene 연결 후 적용)
        chart.sceneProperty().addListener((obs, oldScene, newScene) -> {
            if (newScene != null) {
                Platform.runLater(() -> {
                    for (Node node : chart.lookupAll(".chart-series-line")) {
                        node.setStyle("-fx-stroke-width: 2px;");
                    }
                });
            }
        });

        return chart;
    }

    /**
     * 차트를 테두리 + 제목과 함께 감싸는 컨테이너
     */
    private Region wrapWithBorderTitle(String titleText, Node content) {
        Label title = new Label(titleText);
        title.setFont(Font.font(13));
        title.setStyle("-fx-font-weight: bold;");

        BorderPane container = new BorderPane();
        container.setTop(title);
        BorderPane.setMargin(title, new Insets(6, 8, 4, 8));

        container.setCenter(content);
        BorderPane.setMargin(content, new Insets(0, 6, 6, 6));

        container.setStyle(
                "-fx-border-color: #cfcfcf;" +
                "-fx-border-radius: 6;" +
                "-fx-background-radius: 6;" +
                "-fx-background-color: white;"
        );

        container.setMaxSize(Double.MAX_VALUE, Double.MAX_VALUE);
        return container;
    }
}
