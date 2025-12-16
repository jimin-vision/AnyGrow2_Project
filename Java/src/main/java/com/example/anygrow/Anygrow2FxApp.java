package com.example.anygrow;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.stage.Stage;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalTime;

public class Anygrow2FxApp extends Application {

    private final Anygrow2ClientLogic logic = new Anygrow2ClientLogic();

    private WebSocketClient client;
    private String serverUri;

    private Label statusLabel;

    // 센서 표시
    private Label tempLabel, humLabel, co2Label, illLabel;

    // 경고 표시
    private TextArea alertsArea;

    // 2x2 그래프
    private SensorChartsPane chartsPane;

    // 타이머 패널
    private TimerPanel timerPanel;

    // 타이머 스레드
    private volatile boolean timerThreadRunning = true;
    private volatile String lastSentMode = null;

    @Override
    public void start(Stage stage) {
        var params = getParameters().getRaw();
        serverUri = params.isEmpty() ? "ws://localhost:52273" : params.get(0);

        BorderPane root = new BorderPane();
        root.setPadding(new Insets(10));

        // =========================
        // 상단: 상태바
        // =========================
        HBox topBar = new HBox(10);
        topBar.setAlignment(Pos.CENTER_LEFT);
        statusLabel = new Label("연결 안 됨");
        topBar.getChildren().addAll(new Label("상태:"), statusLabel);
        root.setTop(topBar);

        // =========================
        // 좌측: 센서 값 (큰 글씨)
        // =========================
        VBox leftBox = new VBox(10);
        leftBox.setPadding(new Insets(10));
        leftBox.setMinWidth(240);

        Label sensorTitle = new Label("센서 값");
        sensorTitle.setStyle("-fx-font-size: 16pt; -fx-font-weight: bold;");

        tempLabel = new Label("온도: -- ℃");
        tempLabel.setStyle("-fx-font-size: 14pt;");

        humLabel = new Label("습도: -- %");
        humLabel.setStyle("-fx-font-size: 14pt;");

        co2Label = new Label("CO₂: ---- ppm");
        co2Label.setStyle("-fx-font-size: 14pt;");

        illLabel = new Label("조도: -- lx");
        illLabel.setStyle("-fx-font-size: 14pt;");

        leftBox.getChildren().addAll(sensorTitle, tempLabel, humLabel, co2Label, illLabel);

        // =========================
        // 중앙: 2x2 그래프
        // =========================
        chartsPane = new SensorChartsPane();

        BorderPane center = new BorderPane();
        center.setLeft(leftBox);
        center.setCenter(chartsPane);
        root.setCenter(center);

        // =========================
        // 하단: 타이머 + 경고 + LED 버튼
        // =========================

        // 경고 영역(타이머 옆)
        VBox alertsBox = new VBox(5);
        alertsBox.setPadding(new Insets(10));
        alertsBox.setMinWidth(260);

        Label alertsTitle = new Label("경고");
        alertsTitle.setStyle("-fx-font-weight: bold;");

        alertsArea = new TextArea("센서 데이터 수신 대기 중...");
        alertsArea.setEditable(false);
        alertsArea.setWrapText(true);
        VBox.setVgrow(alertsArea, Priority.ALWAYS);

        alertsBox.getChildren().addAll(alertsTitle, alertsArea);

        // 타이머 패널
        TimerProfileStore store = new TimerProfileStore("anygrow2_timer_profiles.dat");
        timerPanel = new TimerPanel(store);

        // 타이머 + 경고 나란히
        HBox bottomTop = new HBox(10, timerPanel, alertsBox);
        HBox.setHgrow(timerPanel, Priority.ALWAYS);
        HBox.setHgrow(alertsBox, Priority.ALWAYS);

        // LED 버튼 바
        Button btnOff = new Button("LED 끄기");
        Button btnMood = new Button("무드 모드");
        Button btnOn = new Button("LED 켜기");

        btnOff.setOnAction(e -> sendSerialWrite("Off"));
        btnMood.setOnAction(e -> sendSerialWrite("Mood"));
        btnOn.setOnAction(e -> sendSerialWrite("On"));

        HBox ledBar = new HBox(10, btnOff, btnMood, btnOn);
        ledBar.setAlignment(Pos.CENTER);
        ledBar.setPadding(new Insets(10, 0, 0, 0));

        VBox bottom = new VBox(10, bottomTop, ledBar);
        bottom.setPadding(new Insets(10, 0, 0, 0));
        root.setBottom(bottom);

        // =========================
        // Scene/Stage
        // =========================
        Scene scene = new Scene(root, 1200, 720);
        stage.setTitle("Anygrow2 JavaFX 클라이언트 (" + serverUri + ")");
        stage.setScene(scene);
        stage.show();

        stage.setOnCloseRequest(e -> {
            timerThreadRunning = false;
            if (client != null) {
                try {
                    client.close();
                } catch (Exception ignored) {}
            }
            Platform.exit();
        });

        // WebSocket 연결 + 타이머 스레드 시작
        connectWebSocket();
        startTimerThread();
    }

    // =========================
    // WebSocket 연결
    // =========================
    private void connectWebSocket() {
        try {
            client = new WebSocketClient(new URI(serverUri)) {
                @Override
                public void onOpen(ServerHandshake handshakedata) {
                    Platform.runLater(() -> statusLabel.setText("연결됨"));
                }

                @Override
                public void onMessage(String message) {
                    if (!message.startsWith("serial_recive:")) return;

                    String data = message.substring("serial_recive:".length());
                    logic.onSerialReceive(data);

                    // Node.js 방식과 유사하게, 특정 패턴이 보이면 수신 완료 ack
                    if (data.contains("ff,ff") && client != null && client.isOpen()) {
                        client.send("comm_state:sensor data response");
                    }

                    double t = logic.getTemperature();
                    double h = logic.getHumidity();
                    double c = logic.getCo2();
                    double l = logic.getIllumination();

                    Platform.runLater(() -> {
                        updateSensorLabels(t, h, c, l);
                        chartsPane.addPoint(t, h, c, l);
                        updateAlerts(t, h, c, l);
                    });
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    Platform.runLater(() -> statusLabel.setText("연결 종료됨"));
                }

                @Override
                public void onError(Exception ex) {
                    Platform.runLater(() -> statusLabel.setText("오류: " + ex.getMessage()));
                }
            };

            statusLabel.setText("연결 중...");
            client.connect();

        } catch (URISyntaxException e) {
            statusLabel.setText("서버 주소 오류: " + serverUri);
        }
    }

    // =========================
    // 서버로 LED 제어 명령 전송
    // =========================
    private void sendSerialWrite(String mode) {
        if (client == null || !client.isOpen()) return;
        client.send("serial_write:" + mode);
    }

    // =========================
    // 타이머 스레드 (원하는 모드로 자동 전송)
    // =========================
    private void startTimerThread() {
        Thread t = new Thread(() -> {
            while (timerThreadRunning) {
                try {
                    if (client != null && client.isOpen() && timerPanel != null) {
                        String desired = timerPanel.desiredMode(LocalTime.now().withSecond(0).withNano(0));
                        if (lastSentMode == null || !lastSentMode.equals(desired)) {
                            sendSerialWrite(desired);
                            lastSentMode = desired;
                        }
                    }
                    Thread.sleep(10_000);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                } catch (Exception ignored) {}
            }
        }, "LED-Timer");
        t.setDaemon(true);
        t.start();
    }

    // =========================
    // 센서 라벨 갱신
    // =========================
    private void updateSensorLabels(double temp, double hum, double co2, double ill) {
        tempLabel.setText(String.format("온도: %.1f ℃", temp));
        humLabel.setText(String.format("습도: %.1f %%", hum));
        co2Label.setText(co2 < 6000 ? String.format("CO₂: %.0f ppm", co2) : "CO₂: ---- ppm");
        illLabel.setText(String.format("조도: %.0f lx", ill));
    }

    // =========================
    // 경고 갱신
    // =========================
    private void updateAlerts(double temp, double hum, double co2, double ill) {
        StringBuilder sb = new StringBuilder();

        if (temp > 30) sb.append("⚠ 온도가 높습니다: ").append(String.format("%.1f", temp)).append(" ℃\n");
        if (temp < 10) sb.append("⚠ 온도가 낮습니다: ").append(String.format("%.1f", temp)).append(" ℃\n");

        if (hum > 80) sb.append("⚠ 습도가 높습니다: ").append(String.format("%.1f", hum)).append(" %\n");
        if (hum < 30) sb.append("⚠ 습도가 낮습니다: ").append(String.format("%.1f", hum)).append(" %\n");

        if (co2 > 2000 && co2 < 6000) sb.append("⚠ CO₂가 높습니다: ").append(String.format("%.0f", co2)).append(" ppm\n");

        if (ill < 100) sb.append("⚠ 조도가 낮습니다: ").append(String.format("%.0f", ill)).append(" lx\n");

        if (sb.length() == 0) sb.append("현재 경고가 없습니다.");
        alertsArea.setText(sb.toString());
    }

    public static void main(String[] args) {
        launch(args);
    }
}
