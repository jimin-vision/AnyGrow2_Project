package com.example.anygrow;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import javax.swing.*;
import java.awt.*;
import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;

/**
 * JFrame 기반 GUI 클라이언트.
 * - WebSocketClient는 내부 필드로 두고, 이 클래스는 순수 JFrame을 상속합니다.
 * - 기능:
 *   - 센서 값 표시
 *   - 센서 히스토리 그래프 (가로 방향, 시간 흐름, 라인형)
 *   - 그래프 오른쪽에 경고 표시
 *   - LED 타이머(켜는 시간/끄는 시간/모드) + LED OFF/ON/MOOD 버튼
 */
public class Anygrow2GuiFrame extends JFrame {

    private final Anygrow2ClientLogic logic = new Anygrow2ClientLogic();
    private WebSocketClient client;

    // GUI 컴포넌트 (상태/센서)
    private JLabel lblStatus;
    private JLabel lblTemp;
    private JLabel lblHum;
    private JLabel lblCo2;
    private JLabel lblIll;

    // 그래프 & 경고
    private SensorChartPanel chartPanel;
    private JTextArea txtAlerts;

    // 타이머 관련 컴포넌트
    private JTextField txtOnTime;
    private JTextField txtOffTime;
    private JComboBox<String> comboOnMode;
    private JCheckBox chkEnableTimer;

    // 타이머 내부 상태
    private volatile LocalTime scheduledOnTime;
    private volatile LocalTime scheduledOffTime;
    private volatile String scheduledOnMode = "On"; // "On" 또는 "Mood"
    private volatile boolean timerEnabled = false;
    private volatile String lastTimerAction = "";   // "ON" / "OFF" / ""

    private final String serverUri;
    private final DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("HH:mm");

    public Anygrow2GuiFrame(String serverUri) {
        super("Anygrow2 - Java GUI Client");
        this.serverUri = serverUri;

        initGui();
        connectWebSocket();
        startTimerThread();
    }

    /** GUI 초기화 (레이아웃, 컴포넌트 배치) */
    private void initGui() {
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setSize(800, 500);
        setLayout(new BorderLayout());

        // 상단: 상태 표시
        JPanel statusPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        statusPanel.add(new JLabel("Status: "));
        lblStatus = new JLabel("Disconnected");
        statusPanel.add(lblStatus);
        add(statusPanel, BorderLayout.NORTH);

        // --- 중앙: 센서값 + 그래프 + 경고 (모두 하나의 큰 패널 안에) ---
        JPanel centerPanel = new JPanel(new BorderLayout());

        JPanel graphAndAlertPanel = new JPanel(new BorderLayout());
        graphAndAlertPanel.setBorder(BorderFactory.createTitledBorder("Sensor Values / History & Alerts"));

        // 왼쪽: 센서값 + 그래프
        JPanel leftPanel = new JPanel(new BorderLayout());

        // 1) 센서값 표시 (위쪽)
        JPanel sensorPanel = new JPanel(new GridLayout(4, 2, 5, 5));

        lblTemp = new JLabel("-");
        lblHum  = new JLabel("-");
        lblCo2  = new JLabel("-");
        lblIll  = new JLabel("-");

        sensorPanel.add(new JLabel("Temperature (°C):"));
        sensorPanel.add(lblTemp);
        sensorPanel.add(new JLabel("Humidity (%):"));
        sensorPanel.add(lblHum);
        sensorPanel.add(new JLabel("CO₂ (ppm):"));
        sensorPanel.add(lblCo2);
        sensorPanel.add(new JLabel("Illumination:"));
        sensorPanel.add(lblIll);

        leftPanel.add(sensorPanel, BorderLayout.NORTH);

        // 2) 그래프 (아래쪽, 가로 방향 / 라인형)
        chartPanel = new SensorChartPanel();
        leftPanel.add(chartPanel, BorderLayout.CENTER);

        graphAndAlertPanel.add(leftPanel, BorderLayout.CENTER);

        // 오른쪽: 경고 패널
        JPanel alertPanel = new JPanel(new BorderLayout());
        alertPanel.setPreferredSize(new Dimension(220, 0)); // 오른쪽 폭 고정
        alertPanel.setBorder(BorderFactory.createTitledBorder("Alerts"));

        txtAlerts = new JTextArea();
        txtAlerts.setEditable(false);
        txtAlerts.setLineWrap(true);
        txtAlerts.setWrapStyleWord(true);
        txtAlerts.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 12));
        txtAlerts.setText("센서 데이터 수신 대기 중...");
        JScrollPane alertScroll = new JScrollPane(txtAlerts);
        alertPanel.add(alertScroll, BorderLayout.CENTER);

        graphAndAlertPanel.add(alertPanel, BorderLayout.EAST);

        centerPanel.add(graphAndAlertPanel, BorderLayout.CENTER);

        add(centerPanel, BorderLayout.CENTER);

        // --- 하단: 타이머 + LED 버튼 ---
        JPanel bottomPanel = new JPanel(new BorderLayout());

        // 1) LED 타이머 패널
        JPanel timerPanel = new JPanel();
        timerPanel.setBorder(BorderFactory.createTitledBorder("LED Timer (HH:mm)"));
        timerPanel.setLayout(new GridBagLayout());
        GridBagConstraints gc = new GridBagConstraints();
        gc.insets = new Insets(2, 4, 2, 4);
        gc.anchor = GridBagConstraints.WEST;

        // ON 시간
        gc.gridx = 0; gc.gridy = 0;
        timerPanel.add(new JLabel("ON Time:"), gc);

        gc.gridx = 1;
        txtOnTime = new JTextField(5);
        txtOnTime.setText("08:00"); // 기본값
        timerPanel.add(txtOnTime, gc);

        // ON 모드 선택 (On / Mood)
        gc.gridx = 2;
        timerPanel.add(new JLabel("Mode:"), gc);

        gc.gridx = 3;
        comboOnMode = new JComboBox<>(new String[]{"On", "Mood"});
        comboOnMode.setSelectedItem("On");
        timerPanel.add(comboOnMode, gc);

        // OFF 시간
        gc.gridx = 0; gc.gridy = 1;
        timerPanel.add(new JLabel("OFF Time:"), gc);

        gc.gridx = 1;
        txtOffTime = new JTextField(5);
        txtOffTime.setText("22:00"); // 기본값
        timerPanel.add(txtOffTime, gc);

        // 타이머 활성화 체크박스
        gc.gridx = 2;
        chkEnableTimer = new JCheckBox("Enable Timer");
        timerPanel.add(chkEnableTimer, gc);

        // 적용 버튼
        gc.gridx = 3;
        JButton btnApplyTimer = new JButton("Apply");
        btnApplyTimer.addActionListener(e -> applyTimerSettings());
        timerPanel.add(btnApplyTimer, gc);

        // 2) LED 제어 버튼 패널
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 10, 10));
        JButton btnOff  = new JButton("LED OFF");
        JButton btnOn   = new JButton("LED ON");
        JButton btnMood = new JButton("LED MOOD");

        btnOff.addActionListener(e -> {
            sendSerialWrite("Off");
            lastTimerAction = ""; // 수동 조작 시 타이머 state 초기화
        });
        btnOn.addActionListener(e -> {
            sendSerialWrite("On");
            lastTimerAction = "";
        });
        btnMood.addActionListener(e -> {
            sendSerialWrite("Mood");
            lastTimerAction = "";
        });

        buttonPanel.add(btnOff);
        buttonPanel.add(btnOn);
        buttonPanel.add(btnMood);

        bottomPanel.add(timerPanel, BorderLayout.CENTER);
        bottomPanel.add(buttonPanel, BorderLayout.SOUTH);

        add(bottomPanel, BorderLayout.SOUTH);

        setLocationRelativeTo(null); // 화면 중앙
    }

    /** 타이머 설정 적용 (텍스트 필드 → 내부 LocalTime, 모드, 활성화 플래그) */
    private void applyTimerSettings() {
        String onStr = txtOnTime.getText().trim();
        String offStr = txtOffTime.getText().trim();
        String modeStr = (String) comboOnMode.getSelectedItem();

        try {
            LocalTime on = LocalTime.parse(onStr, timeFormatter);
            LocalTime off = LocalTime.parse(offStr, timeFormatter);

            scheduledOnTime = on.withSecond(0).withNano(0);
            scheduledOffTime = off.withSecond(0).withNano(0);
            scheduledOnMode = (modeStr != null) ? modeStr : "On";
            timerEnabled = chkEnableTimer.isSelected();
            lastTimerAction = ""; // 설정 바꿀 때마다 리셋

            System.out.println("[TIMER] Applied: ON=" + scheduledOnTime +
                    " (" + scheduledOnMode + "), OFF=" + scheduledOffTime +
                    ", enabled=" + timerEnabled);
            JOptionPane.showMessageDialog(this,
                    "Timer 설정이 적용되었습니다.",
                    "Timer",
                    JOptionPane.INFORMATION_MESSAGE);
        } catch (DateTimeParseException ex) {
            JOptionPane.showMessageDialog(this,
                    "시간 형식이 잘못되었습니다. 예: 08:30, 22:00",
                    "Timer Error",
                    JOptionPane.ERROR_MESSAGE);
        }
    }

    /** WebSocket 연결 설정 및 접속 */
    private void connectWebSocket() {
        try {
            client = new WebSocketClient(new URI(serverUri)) {
                @Override
                public void onOpen(ServerHandshake handshakedata) {
                    System.out.println("[GUI-WS] Connected to server.");
                    SwingUtilities.invokeLater(() -> lblStatus.setText("Connected"));
                }

                @Override
                public void onMessage(String message) {
                    System.out.println("[GUI-WS] recv: " + message);

                    if (message.startsWith("serial_recive:")) {
                        String data = message.substring("serial_recive:".length());

                        // 패킷 파싱
                        logic.onSerialReceive(data);

                        // 패킷 끝(ETX)이 포함되면 서버에 응답
                        if (data.contains("ff,ff")) {
                            send("comm_state:sensor data response");
                        }

                        // 센서값 가져오기
                        double temp = logic.getTemperature();
                        double hum  = logic.getHumidity();
                        double co2  = logic.getCo2();
                        double ill  = logic.getIllumination();

                        // GUI 업데이트
                        SwingUtilities.invokeLater(() -> {
                            lblTemp.setText(String.format("%.1f", temp));
                            lblHum.setText(String.format("%.1f", hum));

                            if (co2 < 6000) {
                                lblCo2.setText(String.format("%.0f", co2));
                            } else {
                                lblCo2.setText("----");
                            }
                            lblIll.setText(String.format("%.0f", ill));

                            // 그래프에 데이터 추가
                            chartPanel.addDataPoint(temp, hum, co2, ill);

                            // 경고 갱신
                            updateAlerts(temp, hum, co2, ill);
                        });
                    }
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    System.out.println("[GUI-WS] Connection closed: code=" + code + " reason=" + reason);
                    SwingUtilities.invokeLater(() -> lblStatus.setText("Closed"));
                }

                @Override
                public void onError(Exception ex) {
                    System.err.println("[GUI-WS] error: " + ex.getMessage());
                    ex.printStackTrace();
                    SwingUtilities.invokeLater(() -> lblStatus.setText("Error"));
                }
            };

            lblStatus.setText("Connecting...");
            Thread t = new Thread(() -> {
                try {
                    client.connectBlocking();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "WS-Connect");
            t.setDaemon(true);
            t.start();

        } catch (URISyntaxException e) {
            e.printStackTrace();
            lblStatus.setText("Bad URI");
        }
    }

    /** LED 제어 (Off / Mood / On) */
    private void sendSerialWrite(String mode) {
        if (client == null || !client.isOpen()) {
            System.out.println("[GUI-WS] WebSocket not connected, cannot send " + mode);
            return;
        }
        String msg = "serial_write:" + mode;
        System.out.println("[GUI-WS] send: " + msg);
        client.send(msg);
    }

    /** LED 타이머 스레드: 매 10초마다 현재 시간과 ON/OFF 시간을 비교해서 명령 전송 */
    private void startTimerThread() {
        Thread t = new Thread(() -> {
            while (true) {
                try {
                    if (timerEnabled &&
                            scheduledOnTime != null &&
                            scheduledOffTime != null &&
                            client != null &&
                            client.isOpen()) {

                        LocalTime now = LocalTime.now().withSecond(0).withNano(0);

                        // ON 시간
                        if (now.equals(scheduledOnTime) && !"ON".equals(lastTimerAction)) {
                            System.out.println("[TIMER] ON time reached: " + now +
                                    " mode=" + scheduledOnMode);
                            sendSerialWrite(scheduledOnMode);
                            lastTimerAction = "ON";
                        }

                        // OFF 시간
                        if (now.equals(scheduledOffTime) && !"OFF".equals(lastTimerAction)) {
                            System.out.println("[TIMER] OFF time reached: " + now);
                            sendSerialWrite("Off");
                            lastTimerAction = "OFF";
                        }
                    }

                    Thread.sleep(10_000); // 10초마다 체크
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }, "LED-Timer");
        t.setDaemon(true);
        t.start();
    }

    /** 경고 메시지 갱신 */
    private void updateAlerts(double temp, double hum, double co2, double ill) {
        StringBuilder sb = new StringBuilder();

        // 임계값은 예시 값입니다. 필요하면 자유롭게 조정 가능.
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

        // 조도는 용도에 따라 기준이 달라서, 예시로 아주 낮을 때만 경고
        if (ill < 100.0) {
            sb.append("⚠ 조도 낮음: ").append(String.format("%.0f", ill)).append("\n");
        }

        if (sb.length() == 0) {
            sb.append("모든 센서 값이 정상 범위입니다.");
        }

        txtAlerts.setText(sb.toString());
    }

    /** 센서 히스토리를 그리는 커스텀 패널 (라인 그래프 + 두꺼운 선) */
    private static class SensorChartPanel extends JPanel {
        private static final int MAX_POINTS = 200;

        private final List<Double> temps = new ArrayList<>();
        private final List<Double> hums  = new ArrayList<>();
        private final List<Double> co2s  = new ArrayList<>();
        private final List<Double> ills  = new ArrayList<>();

        public SensorChartPanel() {
            setBackground(Color.WHITE);
        }

        public synchronized void addDataPoint(double t, double h, double c, double l) {
            temps.add(t);
            hums.add(h);
            co2s.add(c);
            ills.add(l);

            if (temps.size() > MAX_POINTS) {
                temps.remove(0);
                hums.remove(0);
                co2s.remove(0);
                ills.remove(0);
            }
            repaint();
        }

        @Override
        protected synchronized void paintComponent(Graphics g) {
            super.paintComponent(g);
            Graphics2D g2 = (Graphics2D) g.create();

            int w = getWidth();
            int h = getHeight();
            if (w <= 40 || h <= 40) {
                g2.dispose();
                return;
            }

            // 선 두께 조금 두껍게
            g2.setStroke(new BasicStroke(2f));

            int left = 40;
            int right = w - 10;
            int top = 10;
            int bottom = h - 20;

            int n = temps.size();
            if (n < 2) {
                // 데이터가 2개 미만이면 축만 그린다
                g2.setColor(Color.LIGHT_GRAY);
                g2.drawRect(left, top, right - left, bottom - top);
                g2.dispose();
                return;
            }

            // 전체 값 범위 계산 (모든 센서 값 포함)
            double min = Double.MAX_VALUE;
            double max = -Double.MAX_VALUE;
            for (int i = 0; i < n; i++) {
                min = Math.min(min, temps.get(i));
                min = Math.min(min, hums.get(i));
                min = Math.min(min, co2s.get(i));
                min = Math.min(min, ills.get(i));

                max = Math.max(max, temps.get(i));
                max = Math.max(max, hums.get(i));
                max = Math.max(max, co2s.get(i));
                max = Math.max(max, ills.get(i));
            }
            if (min == max) {
                // 모든 값이 같으면 범위를 조금 늘려준다
                min -= 1.0;
                max += 1.0;
            }
            double range = max - min;

            // 축
            g2.setColor(Color.LIGHT_GRAY);
            g2.drawRect(left, top, right - left, bottom - top);
            g2.drawString("Time →", (left + right) / 2 - 20, bottom + 15);

            // Y축 눈금 간단 표시
            g2.setColor(Color.GRAY);
            for (int i = 0; i <= 4; i++) {
                int y = bottom - (int) ((bottom - top) * (i / 4.0));
                double val = min + range * (i / 4.0);
                g2.drawLine(left, y, right, y);
                g2.drawString(String.format("%.0f", val), 5, y + 4);
            }

            // X좌표 계산용
            double stepX = (right - left) / (double) (n - 1);

            // 센서별 색상 및 라벨
            // 온도 - RED
            drawLine(g2, temps, left, bottom, top, stepX, min, range, new Color(255, 80, 80));
            // 습도 - BLUE
            drawLine(g2, hums, left, bottom, top, stepX, min, range, new Color(80, 80, 255));
            // CO2 - GREEN
            drawLine(g2, co2s, left, bottom, top, stepX, min, range, new Color(60, 160, 60));
            // 조도 - ORANGE
            drawLine(g2, ills, left, bottom, top, stepX, min, range, new Color(240, 160, 60));

            // 범례
            int legendX = right - 110;
            int legendY = top + 15;
            g2.setColor(Color.BLACK);
            g2.drawString("Temp", legendX, legendY);
            g2.setColor(new Color(255, 80, 80));
            g2.drawLine(legendX - 30, legendY - 4, legendX - 5, legendY - 4);

            legendY += 15;
            g2.setColor(Color.BLACK);
            g2.drawString("Hum", legendX, legendY);
            g2.setColor(new Color(80, 80, 255));
            g2.drawLine(legendX - 30, legendY - 4, legendX - 5, legendY - 4);

            legendY += 15;
            g2.setColor(Color.BLACK);
            g2.drawString("CO₂", legendX, legendY);
            g2.setColor(new Color(60, 160, 60));
            g2.drawLine(legendX - 30, legendY - 4, legendX - 5, legendY - 4);

            legendY += 15;
            g2.setColor(Color.BLACK);
            g2.drawString("Illum", legendX, legendY);
            g2.setColor(new Color(240, 160, 60));
            g2.drawLine(legendX - 30, legendY - 4, legendX - 5, legendY - 4);

            g2.dispose();
        }

        private void drawLine(Graphics2D g2,
                              List<Double> values,
                              int left, int bottom, int top,
                              double stepX,
                              double min, double range,
                              Color color) {

            g2.setColor(color);
            int n = values.size();
            int prevX = left;
            int prevY = bottom - (int) ((values.get(0) - min) / range * (bottom - top));

            for (int i = 1; i < n; i++) {
                int x = left + (int) (stepX * i);
                int y = bottom - (int) ((values.get(i) - min) / range * (bottom - top));
                g2.drawLine(prevX, prevY, x, y);
                prevX = x;
                prevY = y;
            }
        }
    }

    /** 실행용 main – JFrame 구동 */
    public static void main(String[] args) {
        String uri = args.length > 0 ? args[0] : "ws://localhost:52273";

        SwingUtilities.invokeLater(() -> {
            Anygrow2GuiFrame frame = new Anygrow2GuiFrame(uri);
            frame.setVisible(true);
        });
    }
}
