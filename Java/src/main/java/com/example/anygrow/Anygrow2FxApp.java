package com.example.anygrow;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
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
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/**
 * Anygrow2 JavaFX GUI Client
 *
 * 기능:
 *  - Anygrow2Server(Java)와 WebSocket으로 직접 통신
 *  - 센서 값 표시 (온도 / 습도 / CO₂ / 조도)
 *  - 센서 4개 라인 차트
 *  - 임계값 기반 경고 영역
 *  - LED 제어 버튼: OFF / ON / MOOD
 *  - LED 타이머:
 *      * 프로필 5개
 *      * 각 프로필당 최대 3개의 시간 구간(세그먼트)
 *      * 세그먼트별 모드: "On" 또는 "Mood"
 *      * 어떤 세그먼트에도 속하지 않는 시간대는 기본적으로 "Off"
 *  - 24시간 타임라인:
 *      * 기본: OFF = 회색
 *      * ON 구간 = 초록색
 *      * MOOD 구간 = 파란색
 *
 *  변경 사항:
 *      - 경고(Alerts) 창을 중앙 오른쪽에서 아래쪽 타이머 옆으로 이동
 *      - 중앙 영역은 그래프가 더 넓게 사용
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

    // --- 그래프 ---
    private XYChart.Series<Number, Number> tempSeries = new XYChart.Series<>();
    private XYChart.Series<Number, Number> humSeries  = new XYChart.Series<>();
    private XYChart.Series<Number, Number> co2Series  = new XYChart.Series<>();
    private XYChart.Series<Number, Number> illSeries  = new XYChart.Series<>();
    private int sampleIndex = 0;

    // --- 타이머 & 프로필 (멀티 세그먼트) ---

    private static final int MAX_SEGMENTS = 3;

    private static class TimerSegment {
        LocalTime start;
        LocalTime end;
        String mode;    // "On" or "Mood"
    }

    private static class TimerProfile {
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
    private TextField[] segStartFields = new TextField[MAX_SEGMENTS];
    private TextField[] segEndFields   = new TextField[MAX_SEGMENTS];
    private ComboBox<String>[] segModeCombos = new ComboBox[MAX_SEGMENTS];

    // 타임라인 캔버스
    private Canvas timerCanvas;

    // 타이머 스레드
    private volatile boolean timerThreadRunning = true;
    // 마지막으로 서버에 전송한 모드 ("Off" / "On" / "Mood")
    private volatile String lastSentMode = null;

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

        // 좌측: 센서 값
       // 좌측: 센서 값
        VBox leftBox = new VBox(10);
        leftBox.setPadding(new Insets(10));
        leftBox.setMinWidth(220);

        // 제목 라벨 (조금 더 크게 + 굵게)
        Label sensorTitle = new Label("Sensor Values");
        sensorTitle.setStyle("-fx-font-size: 16pt; -fx-font-weight: bold;");

        // 센서 값 라벨 (기존보다 크게)
        tempLabel = new Label("Temperature: -- °C");
        tempLabel.setStyle("-fx-font-size: 14pt;");

        humLabel  = new Label("Humidity: -- %");
        humLabel.setStyle("-fx-font-size: 14pt;");

        co2Label  = new Label("CO₂: ---- ppm");
        co2Label.setStyle("-fx-font-size: 14pt;");

        illLabel  = new Label("Illumination: -- lx");
        illLabel.setStyle("-fx-font-size: 14pt;");

        // VBox에 추가
        leftBox.getChildren().addAll(
                sensorTitle,
                tempLabel,
                humLabel,
                co2Label,
                illLabel
        );


        // 중앙: 그래프
        NumberAxis xAxis = new NumberAxis();
        xAxis.setLabel("Samples");
        NumberAxis yAxis = new NumberAxis();
        yAxis.setLabel("Value");

        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setCreateSymbols(false);
        chart.setAnimated(false);
        chart.setLegendVisible(true);

        tempSeries.setName("Temp");
        humSeries.setName("Hum");
        co2Series.setName("CO₂");
        illSeries.setName("Illum");
        chart.getData().addAll(tempSeries, humSeries, co2Series, illSeries);

        // 우측: 경고 영역 (이제 중앙이 아니라, 아래쪽으로 내려서 재사용할 예정)
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

        // 중앙 패널 합치기 (이제 오른쪽에는 아무 것도 두지 않음)
        BorderPane centerPanel = new BorderPane();
        centerPanel.setLeft(leftBox);
        centerPanel.setCenter(chart);
        // centerPanel.setRight(rightBox);  // 경고창은 아래로 이동

        root.setCenter(centerPanel);

        // 하단: 타이머 + (경고창) + LED 버튼
        VBox bottomBox = new VBox(10);
        bottomBox.setPadding(new Insets(10, 0, 0, 0));

        VBox timerPanel = buildTimerPanel();

        // 타이머와 경고창을 가로로 나란히 배치
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

        // WebSocket + 타이머 스레드 시작
        connectWebSocket();
        startTimerThread();

        // 타임라인 초기 그리기
        redrawTimeline();
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
                seg.mode  = mode;  // "On" 또는 "Mood"

                p.segments[i] = seg;
            }

            profiles[idx] = p;
            activeProfile = p;
            lastSentMode = null; // 다음 타이머 체크 때 다시 전송 가능하도록 초기화

            lblActiveProfile.setText(
                    "Active profile: #" + slot + " - " + p.name +
                    " (enabled=" + p.enabled + ")"
            );

            redrawTimeline();

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
                    // 하루 전체 구간
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

                        // 기본 모드 = Off
                        String desiredMode = "Off";

                        // 현재 시간이 어떤 세그먼트에 포함되는지 확인
                        for (int i = 0; i < MAX_SEGMENTS; i++) {
                            TimerSegment seg = p.segments[i];
                            if (seg == null) continue;

                            if (isWithinSegment(now, seg.start, seg.end)) {
                                desiredMode = seg.mode; // "On" 또는 "Mood"
                                break;
                            }
                        }

                        // 모드가 바뀌었을 때만 서버로 전송
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
     *
     * - start == end : 하루 전체(true)
     * - start < end  : 일반 구간 → start <= now < end
     * - start > end  : 자정 넘어가는 구간 → now >= start 또는 now < end
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

    public static void main(String[] args) {
        launch(args);
    }
}
