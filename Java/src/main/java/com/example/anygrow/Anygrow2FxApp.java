package com.example.anygrow;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Node;
import javafx.scene.Scene;
import javafx.scene.canvas.Canvas;
import javafx.scene.canvas.GraphicsContext;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.stage.Stage;
import javafx.util.StringConverter;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.io.*;
import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/**
 * Anygrow2 JavaFX GUI Client
 *
 * 기능:
 *  - Anygrow2Server(Java)와 WebSocket으로 통신
 *  - 센서 값 표시 (온도 / 습도 / CO₂ / 조도)
 *  - 센서별 라인 차트 (2x2 배치)
 *  - 임계값 기반 경고 영역
 *  - LED 제어 버튼: OFF / ON / MOOD
 *  - LED 타이머:
 *      * 프로필 5개
 *      * 각 프로필당 최대 3개의 시간 구간(세그먼트)
 *      * 세그먼트별 모드: "On" 또는 "Mood"
 *      * 세그먼트 밖은 기본적으로 "Off"
 *  - 24시간 타임라인 (OFF = 회색, ON = 초록, MOOD = 파랑)
 *  - 타이머 프로필을 파일(anygrow2_timer_profiles.dat)에 저장/로드
 */
public class Anygrow2FxApp extends Application {

    // --- 센서 파싱 로직 ---
    private final Anygrow2ClientLogic logic = new Anygrow2ClientLogic();

    // --- WebSocket ---
    private WebSocketClient client;
    private String serverUri;   // 예: ws://localhost:52273

    // --- 상태/센서/경고 UI ---
    private Label statusLabel;
    private Label tempLabel;
    private Label humLabel;
    private Label co2Label;
    private Label illLabel;
    private TextArea alertsArea;

    // --- 그래프 시리즈 ---
    private final XYChart.Series<Number, Number> tempSeries = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> humSeries  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> co2Series  = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> illSeries  = new XYChart.Series<>();
    private int sampleIndex = 0;

    // --- 타이머 & 프로필 (멀티 세그먼트) ---
    private static final int MAX_SEGMENTS = 3;
    private static final String PROFILE_SAVE_FILE = "anygrow2_timer_profiles.dat";

    private static class TimerSegment implements Serializable {
        private static final long serialVersionUID = 1L;
        LocalTime start;
        LocalTime end;
        String mode;    // "On" or "Mood"
    }

    private static class TimerProfile implements Serializable {
        private static final long serialVersionUID = 1L;
        String name;
        TimerSegment[] segments = new TimerSegment[MAX_SEGMENTS];
        boolean enabled;
    }

    private final TimerProfile[] profiles = new TimerProfile[5];
    private TimerProfile activeProfile;

    // 타이머 UI 컨트롤
    private ComboBox<Integer> comboProfileSlot;
    private TextField txtProfileName;
    private CheckBox chkTimerEnabled;
    private Label lblActiveProfile;

    // 세그먼트 UI
    private final TextField[] segStartFields = new TextField[MAX_SEGMENTS];
    private final TextField[] segEndFields   = new TextField[MAX_SEGMENTS];
    private final ComboBox<String>[] segModeCombos = new ComboBox[MAX_SEGMENTS];

    // 타임라인 캔버스
    private Canvas timerCanvas;

    // 타이머 스레드
    private volatile boolean timerThreadRunning = true;
    private volatile String lastSentMode = null;   // 마지막 서버에 보낸 LED 모드

    private final DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("HH:mm");

    @Override
    public void start(Stage stage) {
        // --- 서버 URI 결정 ---
        var params = getParameters().getRaw();
        if (params.isEmpty()) {
            serverUri = "ws://localhost:52273";
        } else {
            serverUri = params.get(0);
        }

        // --- 루트 레이아웃 ---
        BorderPane root = new BorderPane();
        root.setPadding(new Insets(10));

        // 상단: 상태바
        HBox topBar = new HBox(10);
        topBar.setAlignment(Pos.CENTER_LEFT);
        Label statusTitle = new Label("Status:");
        statusLabel = new Label("Disconnected");
        topBar.getChildren().addAll(statusTitle, statusLabel);
        root.setTop(topBar);

        // 좌측: 센서 값 (폰트 크게)
        VBox leftBox = new VBox(10);
        leftBox.setPadding(new Insets(10));
        leftBox.setMinWidth(220);

        Label sensorTitle = new Label("Sensor Values");
        sensorTitle.setStyle("-fx-font-size: 16pt; -fx-font-weight: bold;");

        tempLabel = new Label("Temperature: -- °C");
        tempLabel.setStyle("-fx-font-size: 14pt;");

        humLabel  = new Label("Humidity: -- %");
        humLabel.setStyle("-fx-font-size: 14pt;");

        co2Label  = new Label("CO₂: ---- ppm");
        co2Label.setStyle("-fx-font-size: 14pt;");

        illLabel  = new Label("Illumination: -- lx");
        illLabel.setStyle("-fx-font-size: 14pt;");

        leftBox.getChildren().addAll(
                sensorTitle,
                tempLabel,
                humLabel,
                co2Label,
                illLabel
        );

        // 중앙: 센서별 그래프 2x2

        // 온도
        NumberAxis xTempAxis = new NumberAxis();
        xTempAxis.setLabel("Samples");
        NumberAxis yTempAxis = new NumberAxis(0, 50, 10);   // 예시 범위
        yTempAxis.setLabel("Temperature (°C)");
        LineChart<Number, Number> tempChart =
                createSensorChart(xTempAxis, yTempAxis, "Temp", tempSeries);

        // 습도
        NumberAxis xHumAxis = new NumberAxis();
        xHumAxis.setLabel("Samples");
        NumberAxis yHumAxis = new NumberAxis(0, 100, 20);
        yHumAxis.setLabel("Humidity (%)");
        LineChart<Number, Number> humChart =
                createSensorChart(xHumAxis, yHumAxis, "Hum", humSeries);

        // CO₂
        NumberAxis xCo2Axis = new NumberAxis();
        xCo2Axis.setLabel("Samples");
        NumberAxis yCo2Axis = new NumberAxis(0, 6000, 1000);
        yCo2Axis.setLabel("CO₂ (ppm)");
        LineChart<Number, Number> co2Chart =
                createSensorChart(xCo2Axis, yCo2Axis, "CO₂", co2Series);

        // 조도
        NumberAxis xIllAxis = new NumberAxis();
        xIllAxis.setLabel("Samples");
        NumberAxis yIllAxis = new NumberAxis(0, 2000, 500);
        yIllAxis.setLabel("Illumination (lx)");
        LineChart<Number, Number> illChart =
                createSensorChart(xIllAxis, yIllAxis, "Illum", illSeries);

        // 2x2 Grid 레이아웃
        GridPane chartsGrid = new GridPane();
        chartsGrid.setHgap(5);
        chartsGrid.setVgap(5);
        chartsGrid.setPadding(new Insets(0));

        chartsGrid.add(tempChart, 0, 0);
        chartsGrid.add(humChart, 1, 0);
        chartsGrid.add(co2Chart, 0, 1);
        chartsGrid.add(illChart, 1, 1);

        GridPane.setHgrow(tempChart, Priority.ALWAYS);
        GridPane.setHgrow(humChart, Priority.ALWAYS);
        GridPane.setHgrow(co2Chart, Priority.ALWAYS);
        GridPane.setHgrow(illChart, Priority.ALWAYS);
        GridPane.setVgrow(tempChart, Priority.ALWAYS);
        GridPane.setVgrow(humChart, Priority.ALWAYS);
        GridPane.setVgrow(co2Chart, Priority.ALWAYS);
        GridPane.setVgrow(illChart, Priority.ALWAYS);

        // 경고 영역 (Alerts) — 아래쪽으로 이동해서 사용할 예정
        VBox rightBox = new VBox(5);
        rightBox.setPadding(new Insets(10));
        rightBox.setMinWidth(230);

        Label alertsTitle = new Label("Alerts");
        alertsArea = new TextArea();
        alertsArea.setEditable(false);
        alertsArea.setWrapText(true);
        alertsArea.setPrefRowCount(10);
        alertsArea.setText("Waiting for sensor data...");

        rightBox.getChildren().addAll(alertsTitle, alertsArea);
        VBox.setVgrow(alertsArea, Priority.ALWAYS);

        // 중앙 패널: 좌측 센서값 + 중앙 그래프들
        BorderPane centerPanel = new BorderPane();
        centerPanel.setLeft(leftBox);
        centerPanel.setCenter(chartsGrid);

        root.setCenter(centerPanel);

        // 하단: 타이머 + 경고창 + LED 버튼
        VBox bottomBox = new VBox(10);
        bottomBox.setPadding(new Insets(10, 0, 0, 0));

        VBox timerPanel = buildTimerPanel();

        // 타이머와 경고창을 가로로 나란히
        HBox bottomTopRow = new HBox(10);
        bottomTopRow.getChildren().addAll(timerPanel, rightBox);
        HBox.setHgrow(timerPanel, Priority.ALWAYS);
        HBox.setHgrow(rightBox, Priority.ALWAYS);

        bottomBox.getChildren().add(bottomTopRow);

        // LED 버튼들
        HBox ledBar = new HBox(10);
        ledBar.setAlignment(Pos.CENTER);
        ledBar.setPadding(new Insets(10, 0, 0, 0));

        Button btnOff  = new Button("LED OFF");
        Button btnOn   = new Button("LED ON");
        Button btnMood = new Button("LED MOOD");

        btnOff.setOnAction(e -> sendSerialWrite("Off"));
        btnOn.setOnAction(e -> sendSerialWrite("On"));
        btnMood.setOnAction(e -> sendSerialWrite("Mood"));

        ledBar.getChildren().addAll(btnOff, btnOn, btnMood);
        bottomBox.getChildren().add(ledBar);

        root.setBottom(bottomBox);

        // Scene/Stage
        Scene scene = new Scene(root, 1200, 720);
        stage.setTitle("Anygrow2 - JavaFX Client (" + serverUri + ")");
        stage.setScene(scene);
        stage.show();

        // 창 닫을 때 정리
        stage.setOnCloseRequest(e -> {
            timerThreadRunning = false;
            if (client != null) {
                try {
                    client.close();
                } catch (Exception ignored) {}
            }
            Platform.exit();
        });

        // 저장된 프로필 로드
        loadAllProfilesFromDisk();

        // WebSocket + 타이머 스레드 시작
        connectWebSocket();
        startTimerThread();

        // 타임라인 초기 그리기
        redrawTimeline();
    }

    /** 센서 한 개에 대한 라인 차트를 만들어 주는 헬퍼 (2x2 배치용) */
    private LineChart<Number, Number> createSensorChart(NumberAxis xAxis,
                                                        NumberAxis yAxis,
                                                        String seriesName,
                                                        XYChart.Series<Number, Number> series) {
        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setCreateSymbols(false);
        chart.setAnimated(false);
        chart.setLegendVisible(false);
        chart.setMinHeight(120);

        series.setName(seriesName);
        chart.getData().add(series);

        // 선 두께를 조금 두껍게 (Scene에 붙고 나서 스타일 적용)
        chart.sceneProperty().addListener((obs, oldScene, newScene) -> {
            if (newScene != null) {
                Platform.runLater(() -> {
                    for (Node n : chart.lookupAll(".chart-series-line")) {
                        n.setStyle("-fx-stroke-width: 2px;");
                    }
                });
            }
        });

        return chart;
    }

    // ============================================================
    // 타이머 패널 (프로필 + 세그먼트 + 타임라인)
    // ============================================================

    private VBox buildTimerPanel() {
        VBox timerRoot = new VBox(8);
        timerRoot.setPadding(new Insets(10));
        timerRoot.setStyle("-fx-border-color: #cccccc; -fx-border-radius: 4; -fx-border-width: 1;");

        Label title = new Label("LED Timer (하루를 여러 구간으로 나누는 스케줄)");
        title.setStyle("-fx-font-weight: bold;");

        // 프로필 선택/저장/불러오기
        HBox profileRow = new HBox(10);
        profileRow.setAlignment(Pos.CENTER_LEFT);

        comboProfileSlot = new ComboBox<>();
        for (int i = 1; i <= 5; i++) {
            comboProfileSlot.getItems().add(i);
        }
        comboProfileSlot.setValue(1);

        // 콤보박스에 "슬롯 번호: 프로필 이름" 표시
        comboProfileSlot.setConverter(new StringConverter<>() {
            @Override
            public String toString(Integer slot) {
                if (slot == null) return "";
                int idx = slot - 1;
                TimerProfile p = (idx >= 0 && idx < profiles.length) ? profiles[idx] : null;
                String name;
                if (p != null && p.name != null && !p.name.isEmpty()) {
                    name = p.name;
                } else {
                    name = "Profile " + slot;
                }
                return slot + ": " + name;
            }

            @Override
            public Integer fromString(String string) {
                if (string == null || string.isEmpty()) return null;
                int colon = string.indexOf(':');
                String numPart = (colon >= 0 ? string.substring(0, colon) : string).trim();
                try {
                    return Integer.parseInt(numPart);
                } catch (NumberFormatException e) {
                    return null;
                }
            }
        });
        comboProfileSlot.setCellFactory(cb -> new ListCell<>() {
            @Override
            protected void updateItem(Integer item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) {
                    setText(null);
                } else {
                    setText(comboProfileSlot.getConverter().toString(item));
                }
            }
        });
        comboProfileSlot.setButtonCell(new ListCell<>() {
            @Override
            protected void updateItem(Integer item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) {
                    setText(null);
                } else {
                    setText(comboProfileSlot.getConverter().toString(item));
                }
            }
        });

        txtProfileName = new TextField();
        txtProfileName.setPromptText("Profile name");

        Button btnLoad = new Button("Load");
        Button btnSave = new Button("Save");

        btnLoad.setOnAction(e -> loadProfile());
        btnSave.setOnAction(e -> saveProfile());

        profileRow.getChildren().addAll(
                new Label("Profile #"),
                comboProfileSlot,
                new Label("Name:"),
                txtProfileName,
                btnLoad,
                btnSave
        );
        HBox.setHgrow(txtProfileName, Priority.ALWAYS);

        // 세그먼트 입력 영역
        VBox segmentsBox = new VBox(6);
        segmentsBox.setPadding(new Insets(4, 0, 4, 0));
        segmentsBox.getChildren().add(new Label("Segments (구간별 LED ON/MOOD, 구간 밖은 OFF):"));

        for (int i = 0; i < MAX_SEGMENTS; i++) {
            HBox row = new HBox(8);
            row.setAlignment(Pos.CENTER_LEFT);

            Label lblIdx = new Label("#" + (i + 1));

            TextField tfStart = new TextField();
            tfStart.setPromptText("HH:mm");
            tfStart.setPrefWidth(70);

            TextField tfEnd = new TextField();
            tfEnd.setPromptText("HH:mm");
            tfEnd.setPrefWidth(70);

            ComboBox<String> cbMode = new ComboBox<>();
            cbMode.getItems().addAll("On", "Mood");
            cbMode.setPrefWidth(80);

            segStartFields[i] = tfStart;
            segEndFields[i] = tfEnd;
            segModeCombos[i] = cbMode;

            row.getChildren().addAll(
                    lblIdx,
                    new Label("Start:"), tfStart,
                    new Label("End:"), tfEnd,
                    new Label("Mode:"), cbMode
            );

            segmentsBox.getChildren().add(row);
        }

        // 타이머 활성화 체크
        chkTimerEnabled = new CheckBox("Enable Timer");
        chkTimerEnabled.setSelected(false);

        // 타임라인 캔버스
        timerCanvas = new Canvas(650, 60);

        lblActiveProfile = new Label("Active profile: (none)");

        timerRoot.getChildren().addAll(
                title,
                profileRow,
                segmentsBox,
                chkTimerEnabled,
                new Label("24h timeline (OFF = gray, ON = green, MOOD = blue):"),
                timerCanvas,
                lblActiveProfile
        );

        return timerRoot;
    }

    private void refreshProfileComboDisplay() {
        Integer current = comboProfileSlot.getValue();
        comboProfileSlot.setValue(null);
        comboProfileSlot.setValue(current);
    }

    // ============================================================
    // WebSocket
    // ============================================================

    private void connectWebSocket() {
        try {
            URI uri = new URI(serverUri);

            client = new WebSocketClient(uri) {
                @Override
                public void onOpen(ServerHandshake handshakedata) {
                    System.out.println("[FX-WS] Connected to " + serverUri);
                    Platform.runLater(() -> statusLabel.setText("Connected"));
                }

                @Override
                public void onMessage(String message) {
                    System.out.println("[FX-WS] recv: " + message);

                    if (message.startsWith("serial_recive:")) {
                        String data = message.substring("serial_recive:".length());

                        // 센서 데이터 파싱
                        logic.onSerialReceive(data);

                        // 패킷 끝(예: ff,ff)이 오면 응답 한 번 보내는 예시
                        if (data.contains("ff,ff") && client != null && client.isOpen()) {
                            client.send("comm_state:sensor data response");
                        }

                        double temp = logic.getTemperature();
                        double hum  = logic.getHumidity();
                        double co2  = logic.getCo2();
                        double ill  = logic.getIllumination();

                        Platform.runLater(() -> {
                            updateSensorLabels(temp, hum, co2, ill);
                            addChartPoint(temp, hum, co2, ill);
                            updateAlerts(temp, hum, co2, ill);
                        });

                    } else if (message.startsWith("comm_state:")) {
                        String state = message.substring("comm_state:".length());
                        System.out.println("[FX-WS] comm_state from server: " + state);
                    }
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    System.out.println("[FX-WS] Closed: " + code + " / " + reason + " / remote=" + remote);
                    Platform.runLater(() -> statusLabel.setText("Closed"));
                }

                @Override
                public void onError(Exception ex) {
                    System.err.println("[FX-WS] Error: " + ex.getMessage());
                    ex.printStackTrace();
                    Platform.runLater(() -> statusLabel.setText("Error: " + ex.getMessage()));
                }
            };

            statusLabel.setText("Connecting...");
            client.connect();

        } catch (URISyntaxException e) {
            e.printStackTrace();
            statusLabel.setText("Bad URI: " + serverUri);
        }
    }

    private void sendSerialWrite(String mode) {
        if (client == null || !client.isOpen()) {
            System.out.println("[FX-WS] Cannot send, websocket not open. mode=" + mode);
            return;
        }
        String msg = "serial_write:" + mode;
        System.out.println("[FX-WS] send: " + msg);
        client.send(msg);
    }

    // ============================================================
    // 센서 UI / 그래프 / 경고
    // ============================================================

    private void updateSensorLabels(double temp, double hum, double co2, double ill) {
        tempLabel.setText(String.format("Temperature: %.1f °C", temp));
        humLabel.setText(String.format("Humidity: %.1f %%", hum));

        if (co2 < 6000) {
            co2Label.setText(String.format("CO₂: %.0f ppm", co2));
        } else {
            co2Label.setText("CO₂: ---- ppm");
        }

        illLabel.setText(String.format("Illumination: %.0f lx", ill));
    }

    private void addChartPoint(double temp, double hum, double co2, double ill) {
        int x = sampleIndex++;

        tempSeries.getData().add(new XYChart.Data<>(x, temp));
        humSeries.getData().add(new XYChart.Data<>(x, hum));
        co2Series.getData().add(new XYChart.Data<>(x, co2));
        illSeries.getData().add(new XYChart.Data<>(x, ill));

        trimSeries(tempSeries, 200);
        trimSeries(humSeries, 200);
        trimSeries(co2Series, 200);
        trimSeries(illSeries, 200);
    }

    private void trimSeries(XYChart.Series<Number, Number> series, int maxSize) {
        if (series.getData().size() > maxSize) {
            series.getData().remove(0, series.getData().size() - maxSize);
        }
    }

    private void updateAlerts(double temp, double hum, double co2, double ill) {
        StringBuilder sb = new StringBuilder();

        if (temp > 30.0) {
            sb.append("⚠ 온도 높음: ").append(String.format("%.1f", temp)).append(" °C ( > 30 )\n");
        } else if (temp < 10.0) {
            sb.append("⚠ 온도 낮음: ").append(String.format("%.1f", temp)).append(" °C ( < 10 )\n");
        }

        if (hum > 80.0) {
            sb.append("⚠ 습도 높음: ").append(String.format("%.1f", hum)).append(" % ( > 80 )\n");
        } else if (hum < 30.0) {
            sb.append("⚠ 습도 낮음: ").append(String.format("%.1f", hum)).append(" % ( < 30 )\n");
        }

        if (co2 > 2000.0 && co2 < 6000.0) {
            sb.append("⚠ CO₂ 높음: ").append(String.format("%.0f", co2)).append(" ppm ( > 2000 )\n");
        }

        if (ill < 100.0) {
            sb.append("⚠ 조도 낮음: ").append(String.format("%.0f", ill)).append(" lx\n");
        }

        if (sb.length() == 0) {
            sb.append("모든 센서 값이 정상 범위입니다.");
        }

        alertsArea.setText(sb.toString());
    }

    // ============================================================
    // 타이머: 프로필 저장/불러오기, 타임라인, 스레드
    // ============================================================

    private void saveProfile() {
        Integer slot = comboProfileSlot.getValue();
        if (slot == null) return;
        int idx = slot - 1;

        String name = txtProfileName.getText().trim();
        boolean enabled = chkTimerEnabled.isSelected();

        TimerProfile p = new TimerProfile();
        p.name = name.isEmpty() ? ("Profile " + slot) : name;
        p.enabled = enabled;

        try {
            for (int i = 0; i < MAX_SEGMENTS; i++) {
                String sStart = segStartFields[i].getText().trim();
                String sEnd   = segEndFields[i].getText().trim();
                String mode   = segModeCombos[i].getValue();

                if (sStart.isEmpty() || sEnd.isEmpty() || mode == null) {
                    p.segments[i] = null;
                    continue;
                }

                LocalTime start = LocalTime.parse(sStart, timeFormatter).withSecond(0).withNano(0);
                LocalTime end   = LocalTime.parse(sEnd, timeFormatter).withSecond(0).withNano(0);

                TimerSegment seg = new TimerSegment();
                seg.start = start;
                seg.end   = end;
                seg.mode  = mode;

                p.segments[i] = seg;
            }

            profiles[idx] = p;
            activeProfile = p;
            lastSentMode = null;

            lblActiveProfile.setText(
                    "Active profile: #" + slot + " - " + p.name +
                            " (enabled=" + p.enabled + ")"
            );

            redrawTimeline();

            // 콤보박스 표시 갱신
            refreshProfileComboDisplay();

            // 디스크에 전체 프로필 저장
            saveAllProfilesToDisk();

            Alert info = new Alert(Alert.AlertType.INFORMATION);
            info.setTitle("Timer Profile");
            info.setHeaderText("Profile saved");
            info.setContentText("Profile #" + slot + " 이(가) 저장되었습니다.");
            info.showAndWait();

        } catch (DateTimeParseException ex) {
            Alert alert = new Alert(Alert.AlertType.ERROR);
            alert.setTitle("Timer Error");
            alert.setHeaderText("시간 형식이 잘못되었습니다.");
            alert.setContentText("HH:mm 형식으로 입력해주세요. (예: 06:00, 22:00)");
            alert.showAndWait();
        }
    }

    private void loadProfile() {
        Integer slot = comboProfileSlot.getValue();
        if (slot == null) return;
        int idx = slot - 1;

        TimerProfile p = profiles[idx];
        if (p == null) {
            Alert info = new Alert(Alert.AlertType.INFORMATION);
            info.setTitle("Timer Profile");
            info.setHeaderText("저장된 프로필이 없습니다.");
            info.setContentText("Profile #" + slot + " 은(는) 비어 있습니다.");
            info.showAndWait();
            return;
        }

        txtProfileName.setText(p.name);
        chkTimerEnabled.setSelected(p.enabled);

        for (int i = 0; i < MAX_SEGMENTS; i++) {
            TimerSegment seg = p.segments[i];
            if (seg == null) {
                segStartFields[i].setText("");
                segEndFields[i].setText("");
                segModeCombos[i].setValue(null);
            } else {
                segStartFields[i].setText(seg.start.format(timeFormatter));
                segEndFields[i].setText(seg.end.format(timeFormatter));
                segModeCombos[i].setValue(seg.mode);
            }
        }

        activeProfile = p;
        lastSentMode = null;

        lblActiveProfile.setText(
                "Active profile: #" + slot + " - " + p.name +
                        " (enabled=" + p.enabled + ")"
        );

        redrawTimeline();
        refreshProfileComboDisplay();
    }

    private void redrawTimeline() {
        GraphicsContext g = timerCanvas.getGraphicsContext2D();
        double w = timerCanvas.getWidth();
        double h = timerCanvas.getHeight();

        // 배경 지우기
        g.setFill(Color.WHITE);
        g.fillRect(0, 0, w, h);

        // 기본 OFF 바
        double margin = 30;
        double barX = margin;
        double barY = h / 3.0;
        double barW = w - 2 * margin;
        double barH = h / 3.0;

        g.setFill(Color.LIGHTGRAY);
        g.fillRoundRect(barX, barY, barW, barH, 10, 10);

        TimerProfile p = activeProfile;
        if (p != null) {
            // 세그먼트별로 덮어 그리기
            for (int i = 0; i < MAX_SEGMENTS; i++) {
                TimerSegment seg = p.segments[i];
                if (seg == null) continue;

                double startRatio = seg.start.toSecondOfDay() / (24.0 * 3600.0);
                double endRatio   = seg.end.toSecondOfDay()   / (24.0 * 3600.0);

                Color color = seg.mode.equals("On") ? Color.LIGHTGREEN : Color.LIGHTBLUE;
                g.setFill(color);

                if (startRatio == endRatio) {
                    g.fillRoundRect(barX, barY, barW, barH, 10, 10);
                } else if (startRatio < endRatio) {
                    double x1 = barX + barW * startRatio;
                    double w1 = barW * (endRatio - startRatio);
                    g.fillRoundRect(x1, barY, w1, barH, 10, 10);
                } else {
                    // 자정 넘어가는 구간 (예: 22:00~06:00)
                    double x1 = barX + barW * startRatio;
                    double w1 = barW * (1.0 - startRatio);
                    g.fillRoundRect(x1, barY, w1, barH, 10, 10);

                    double x2 = barX;
                    double w2 = barW * endRatio;
                    g.fillRoundRect(x2, barY, w2, barH, 10, 10);
                }
            }
        }

        // 아래 시간 눈금
        g.setFill(Color.BLACK);
        g.fillText("0h", barX - 15, barY + barH + 18);
        g.fillText("12h", barX + barW / 2 - 15, barY + barH + 18);
        g.fillText("24h", barX + barW - 15, barY + barH + 18);
    }

    private void startTimerThread() {
        Thread t = new Thread(() -> {
            while (timerThreadRunning) {
                try {
                    TimerProfile p = activeProfile;
                    if (p != null && p.enabled && client != null && client.isOpen()) {
                        LocalTime now = LocalTime.now().withSecond(0).withNano(0);

                        String desiredMode = "Off"; // 기본값

                        // 현재 시간이 어떤 세그먼트에 포함되는지 확인
                        for (int i = 0; i < MAX_SEGMENTS; i++) {
                            TimerSegment seg = p.segments[i];
                            if (seg == null) continue;

                            if (isWithinSegment(now, seg.start, seg.end)) {
                                desiredMode = seg.mode; // "On" 또는 "Mood"
                                break;
                            }
                        }

                        if (lastSentMode == null || !lastSentMode.equals(desiredMode)) {
                            System.out.println("[TIMER] Desired LED mode = " + desiredMode + " at " + now);
                            sendSerialWrite(desiredMode);
                            lastSentMode = desiredMode;
                        }
                    }

                    Thread.sleep(10_000); // 10초마다 체크

                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                } catch (Exception ex) {
                    ex.printStackTrace();
                }
            }
        }, "LED-Timer");
        t.setDaemon(true);
        t.start();
    }

    /**
     * now 가 [start, end) 구간 안에 들어가는지 판별 (자정 넘어가는 구간 포함)
     */
    private boolean isWithinSegment(LocalTime now, LocalTime start, LocalTime end) {
        if (start.equals(end)) {
            return true;  // 하루 전체
        }
        if (start.isBefore(end)) {
            return !now.isBefore(start) && now.isBefore(end);
        } else {
            // 예: 22:00 ~ 06:00
            return !now.isBefore(start) || now.isBefore(end);
        }
    }

    // ============================================================
    // 프로필 파일 저장/로드
    // ============================================================

    private void saveAllProfilesToDisk() {
        try (ObjectOutputStream oos =
                     new ObjectOutputStream(new FileOutputStream(PROFILE_SAVE_FILE))) {
            oos.writeObject(profiles);
            System.out.println("[TIMER] Profiles saved to " + PROFILE_SAVE_FILE);
        } catch (IOException e) {
            System.err.println("[TIMER] Failed to save profiles: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void loadAllProfilesFromDisk() {
        File f = new File(PROFILE_SAVE_FILE);
        if (!f.exists()) {
            System.out.println("[TIMER] No profile save file found.");
            return;
        }
        try (ObjectInputStream ois =
                     new ObjectInputStream(new FileInputStream(f))) {
            Object obj = ois.readObject();
            if (obj instanceof TimerProfile[]) {
                TimerProfile[] loaded = (TimerProfile[]) obj;
                for (int i = 0; i < profiles.length && i < loaded.length; i++) {
                    profiles[i] = loaded[i];
                }

                int activeIndex = -1;
                for (int i = 0; i < profiles.length; i++) {
                    if (profiles[i] != null && profiles[i].enabled) {
                        activeIndex = i;
                        break;
                    }
                }
                if (activeIndex == -1) {
                    for (int i = 0; i < profiles.length; i++) {
                        if (profiles[i] != null) {
                            activeIndex = i;
                            break;
                        }
                    }
                }

                if (activeIndex != -1) {
                    activeProfile = profiles[activeIndex];
                    int slotNumber = activeIndex + 1;

                    comboProfileSlot.setValue(slotNumber);
                    txtProfileName.setText(activeProfile.name);
                    chkTimerEnabled.setSelected(activeProfile.enabled);

                    for (int i = 0; i < MAX_SEGMENTS; i++) {
                        TimerSegment seg = activeProfile.segments[i];
                        if (seg == null) {
                            segStartFields[i].setText("");
                            segEndFields[i].setText("");
                            segModeCombos[i].setValue(null);
                        } else {
                            segStartFields[i].setText(seg.start.format(timeFormatter));
                            segEndFields[i].setText(seg.end.format(timeFormatter));
                            segModeCombos[i].setValue(seg.mode);
                        }
                    }

                    lblActiveProfile.setText(
                            "Active profile: #" + slotNumber + " - " + activeProfile.name +
                                    " (enabled=" + activeProfile.enabled + ")"
                    );

                    refreshProfileComboDisplay();
                    System.out.println("[TIMER] Profiles loaded. Active profile #" + slotNumber);
                } else {
                    System.out.println("[TIMER] Profiles loaded, but no active profile.");
                }
            } else {
                System.err.println("[TIMER] Profile save file has unexpected type: " +
                        obj.getClass());
            }

        } catch (Exception e) {
            System.err.println("[TIMER] Failed to load profiles: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        launch(args);
    }
}
