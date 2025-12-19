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

    // ====== 슬라이딩 윈도우 설정 ======
    // 화면에 유지할 포인트 개수 (기존 trim의 max와 동일하게 맞추는 게 좋음)
    private static final int WINDOW_SIZE = 200;

    private final XYChart.Series<Number, Number> tempSeries = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> humSeries  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> co2Series  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> illSeries  = new XYChart.Series<>();

    // 각 차트의 X축을 잡아두고, addPoint 때마다 범위를 이동시킴
    private final NumberAxis tempXAxis = new NumberAxis();
    private final NumberAxis humXAxis  = new NumberAxis();
    private final NumberAxis co2XAxis  = new NumberAxis();
    private final NumberAxis illXAxis  = new NumberAxis();

    private int sampleIndex = 0;

    public SensorChartsPane() {
        setHgap(10);
        setVgap(10);
        setPadding(new Insets(6));

        // 각 X축 공통 설정 (슬라이딩 윈도우용)
        configureSlidingXAxis(tempXAxis, "시간 흐름");
        configureSlidingXAxis(humXAxis,  "시간 흐름");
        configureSlidingXAxis(co2XAxis,  "시간 흐름");
        configureSlidingXAxis(illXAxis,  "시간 흐름");

        // 각 센서별 차트 생성
        LineChart<Number, Number> tempChart =
                createChart(tempXAxis, "온도 (℃)", 0, 50, 10, tempSeries);

        LineChart<Number, Number> humChart =
                createChart(humXAxis, "습도 (%)", 0, 100, 20, humSeries);

        LineChart<Number, Number> co2Chart =
                createChart(co2XAxis, "CO₂ (ppm)", 0, 6000, 1000, co2Series);

        LineChart<Number, Number> illChart =
                createChart(illXAxis, "조도 (lx)", 0, 6000, 1000, illSeries);

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

        // 초기 X축 범위(빈 차트여도 형태 유지)
        updateAllXAxes(0);
    }

    /**
     * 센서 데이터 1회 갱신 시 호출
     * (어떤 스레드에서 호출되더라도 안전하게 UI 스레드에서 처리)
     */
    public void addPoint(double temp, double hum, double co2, double ill) {
        if (Platform.isFxApplicationThread()) {
            addPointOnFxThread(temp, hum, co2, ill);
        } else {
            Platform.runLater(() -> addPointOnFxThread(temp, hum, co2, ill));
        }
    }

    private void addPointOnFxThread(double temp, double hum, double co2, double ill) {
        int x = sampleIndex++;

        tempSeries.getData().add(new XYChart.Data<>(x, temp));
        humSeries.getData().add(new XYChart.Data<>(x, hum));
        co2Series.getData().add(new XYChart.Data<>(x, co2));
        illSeries.getData().add(new XYChart.Data<>(x, ill));

        // 데이터 개수 제한(윈도우 크기와 동일하게 유지)
        trim(tempSeries, WINDOW_SIZE);
        trim(humSeries,  WINDOW_SIZE);
        trim(co2Series,  WINDOW_SIZE);
        trim(illSeries,  WINDOW_SIZE);

        // ★ 슬라이딩 윈도우: X축 범위를 최근 WINDOW_SIZE 구간으로 이동
        updateAllXAxes(x);
    }

    // -----------------------------
    // 내부 유틸
    // -----------------------------
    private void trim(XYChart.Series<Number, Number> s, int max) {
        int size = s.getData().size();
        if (size > max) {
            s.getData().remove(0, size - max);
        }
    }

    private void configureSlidingXAxis(NumberAxis xAxis, String label) {
        xAxis.setLabel(label);

        // 중요: 0을 강제로 포함시키면, 시간이 지날수록 0부터 시작하는 축이 유지되어
        // 선이 오른쪽으로 몰려 "짧아지는" 현상이 생김
        xAxis.setForceZeroInRange(false);

        // 슬라이딩 윈도우는 우리가 bound를 직접 조절
        xAxis.setAutoRanging(false);

        // 보기 좋은 눈금
        xAxis.setTickUnit(Math.max(1, WINDOW_SIZE / 10.0));
        xAxis.setMinorTickCount(4);

        // 초기에 대략적인 범위 부여
        xAxis.setLowerBound(0);
        xAxis.setUpperBound(Math.max(10, WINDOW_SIZE));
    }

    private void updateAllXAxes(int currentX) {
        updateSlidingXAxis(tempXAxis, currentX);
        updateSlidingXAxis(humXAxis,  currentX);
        updateSlidingXAxis(co2XAxis,  currentX);
        updateSlidingXAxis(illXAxis,  currentX);
    }

    private void updateSlidingXAxis(NumberAxis xAxis, int currentX) {
        int upper = Math.max(currentX, WINDOW_SIZE);
        int lower = Math.max(0, upper - WINDOW_SIZE);

        xAxis.setLowerBound(lower);
        xAxis.setUpperBound(upper);
        xAxis.setTickUnit(Math.max(1, WINDOW_SIZE / 10.0));
    }

    private LineChart<Number, Number> createChart(
            NumberAxis xAxis,
            String yLabel,
            double minY,
            double maxY,
            double tickY,
            XYChart.Series<Number, Number> series
    ) {
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
