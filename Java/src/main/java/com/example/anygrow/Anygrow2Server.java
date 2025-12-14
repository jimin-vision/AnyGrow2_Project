package com.example.anygrow;

import com.example.anygrow.SensorDataRepository;
import com.example.anygrow.Anygrow2ClientLogic;

import com.fazecast.jSerialComm.SerialPort;
import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

import java.net.InetSocketAddress;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.*;

/**
 * Anygrow2 서버 (Java 버전)
 *
 * 역할:
 *  - 시리얼 포트(보드)와 통신
 *  - WebSocket(포트 52273)으로 클라이언트(GUI/브라우저)와 통신
 *  - 센서데이터 요청 패킷 주기적 전송
 *  - 센서데이터 수신 → "serial_recive:..." 형식으로 브로드캐스트
 *  - LED 제어: "serial_write:Off/On/Mood" 처리
 */
public class Anygrow2Server extends WebSocketServer {

    // ====== 시리얼 관련 ======
    private SerialPort serialPort;
    private final String serialPortName;

        // 센서 파싱 + DB 저장을 위한 객체
    private final Anygrow2ClientLogic logic = new Anygrow2ClientLogic();
    private final SensorDataRepository sensorRepo = SensorDataRepository.getInstance();

    // Node.js와 동일한 센서 요청 패킷
    // 0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03
    private static final byte[] SENSOR_REQUEST =
            hexStringToBytes("0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03");

    // LED 제어 패킷 (Node.js anygrow2_server.js 기준)
    // Off / Mood / On
    private static final byte[] LED_OFF =
            hexStringToBytes("0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03");
    private static final byte[] LED_MOOD =
            hexStringToBytes("0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03");
    private static final byte[] LED_ON =
            hexStringToBytes("0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03");

    // 센서 요청 상태 관리 (rc_state 비슷한 개념)
    private volatile String rcState = "ok";   // "ok" or "wait"
    private volatile int waitCount = 0;       // 응답 대기 카운트

    // 스케줄러 (센서 요청 주기)
    private final ScheduledExecutorService scheduler =
            Executors.newSingleThreadScheduledExecutor();

    // WebSocket 연결 모음
    private final Set<WebSocket> connections =
            Collections.synchronizedSet(new HashSet<>());

    // ====== 생성자 ======
    public Anygrow2Server(InetSocketAddress address, String serialPortName) {
        super(address);
        this.serialPortName = serialPortName;
    }

    // ====== WebSocketServer 콜백 ======
    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        System.out.println("[WS] Client connected: " + conn.getRemoteSocketAddress());
        connections.add(conn);
    }

    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        System.out.println("[WS] Client disconnected: " + conn.getRemoteSocketAddress()
                + " reason=" + reason);
        connections.remove(conn);
    }

    @Override
    public void onMessage(WebSocket conn, String message) {
        System.out.println("[WS] <- " + message);

        if (message.startsWith("serial_write:")) {
            String mode = message.substring("serial_write:".length()).trim();
            handleSerialWrite(mode);
        } else if (message.startsWith("comm_state:")) {
            // 클라이언트가 센서데이터 처리 완료 응답
            // Node.js에서 "comm_state:sensor data response"를 받으면 rc_state = "ok"
            System.out.println("[SERVER] comm_state 수신 → rcState=ok");
            rcState = "ok";
            waitCount = 0;
        }
    }

    @Override
    public void onError(WebSocket conn, Exception ex) {
        System.err.println("[WS] ERROR: " + ex.getMessage());
        ex.printStackTrace();
    }

    @Override
    public void onStart() {
        System.out.println("[WS] WebSocket server started on " + getAddress());

        try {
            openSerialPort(serialPortName);
            startSerialReader();
            startSensorRequestScheduler();
        } catch (RuntimeException e) {
            System.err.println("[SERVER] 시리얼 초기화 실패: " + e.getMessage());
            e.printStackTrace();
        }
    }

    // ====== 시리얼 포트 열기 ======
    private void openSerialPort(String portName) {
        serialPort = SerialPort.getCommPort(portName);

        // Node.js 설정과 동일: 38400, 8N1, no parity
        serialPort.setComPortParameters(
                38400,                     // baudRate
                8,                         // dataBits
                SerialPort.ONE_STOP_BIT,   // stopBits = 1
                SerialPort.NO_PARITY       // parity = none
        );

        // 타임아웃 설정 (semi-blocking read)
        serialPort.setComPortTimeouts(
                SerialPort.TIMEOUT_READ_SEMI_BLOCKING,
                1000, // 1초
                0
        );

        // 플로우 컨트롤 비활성화
        serialPort.setFlowControl(SerialPort.FLOW_CONTROL_DISABLED);

        if (!serialPort.openPort()) {
            throw new RuntimeException("시리얼 포트 오픈 실패: " + portName);
        }

        System.out.println("[SERVER] SerialPort opened: " + portName +
                " (baud=38400, 8N1)");
    }

    // ====== 센서 요청 스케줄러 ======
    private void startSensorRequestScheduler() {
        scheduler.scheduleAtFixedRate(() -> {
            try {
                if (serialPort == null || !serialPort.isOpen()) {
                    return;
                }

                if ("ok".equals(rcState)) {
                    sendSensorRequest();
                    rcState = "wait";
                    waitCount = 0;
                } else {
                    waitCount++;
                    if (waitCount > 5) { // 약 5초 동안 응답 없으면 다시 ok로
                        System.out.println("[SERVER] 센서 응답 없음, rcState 강제 초기화");
                        rcState = "ok";
                        waitCount = 0;
                    }
                }
            } catch (Exception e) {
                System.err.println("[SERVER] 센서 요청 스케줄러 오류: " + e.getMessage());
                e.printStackTrace();
            }
        }, 0, 1, TimeUnit.SECONDS); // 1초마다 Node.js와 동일
    }

    private void sendSensorRequest() {
        if (serialPort == null || !serialPort.isOpen()) return;
        int written = serialPort.writeBytes(SENSOR_REQUEST, SENSOR_REQUEST.length);
        System.out.println("[SERVER] 센서데이터 요청 전송 (Java), bytes=" + written);
    }

    // ====== 시리얼 수신 스레드 ======
   private void startSerialReader() {
    Thread t = new Thread(() -> {
        byte[] buffer = new byte[256];

        while (serialPort != null && serialPort.isOpen()) {
            try {
                int available = serialPort.bytesAvailable();
                if (available <= 0) {
                    Thread.sleep(10);
                    continue;
                }
                if (available > buffer.length) {
                    available = buffer.length;
                }

                int numRead = serialPort.readBytes(buffer, available);
                if (numRead > 0) {
                    String hex = toHexWithCommas(buffer, numRead);
                    System.out.println("[SERVER] 센서데이터 수신 (Java): " + hex);

                    // 1) WebSocket 클라이언트로 그대로 전달
                    broadcastToClients("serial_recive:" + hex);

                    // 2) 센서 응답이 왔으니 상태 초기화
                    rcState = "ok";
                    waitCount = 0;

                    // 3) 패킷이 완전한 센서 데이터인 경우에만 파싱 + DB 저장
                    //    (프로토콜 상 ff,ff 가 패킷 끝에 들어오는 것에 맞춰 사용)
                    if (hex.contains("ff,ff")) {
                        try {
                            // Anygrow2ClientLogic 재활용해서 센서 값 파싱
                            logic.onSerialReceive(hex);
                            double temp = logic.getTemperature();
                            double hum  = logic.getHumidity();
                            double co2  = logic.getCo2();
                            double ill  = logic.getIllumination();

                            // DB에 한 줄 저장 (최근 24시간 유지하도록 구현한 버전이라면 내부에서 auto-clean)
                            sensorRepo.saveReading(temp, hum, co2, ill);
                        } catch (Exception ex) {
                            System.err.println("[SERVER] 센서 데이터 DB 저장 중 오류: " + ex.getMessage());
                            ex.printStackTrace();
                        }
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                System.err.println("[SERVER] 시리얼 수신 오류: " + e.getMessage());
                e.printStackTrace();
            }
        }

        System.out.println("[SERVER] 시리얼 리더 스레드 종료");
    }, "SerialReader");
    t.setDaemon(true);
    t.start();
}

    // ====== LED 제어 처리 ======
    private void handleSerialWrite(String mode) {
        if (serialPort == null || !serialPort.isOpen()) {
            System.out.println("[SERVER] 시리얼 포트가 열려있지 않아 LED 제어 불가");
            return;
        }

        byte[] packet;
        switch (mode.toLowerCase()) {
            case "off":
                packet = LED_OFF;
                System.out.println("[SERVER] LED 제어: OFF");
                break;
            case "mood":
                packet = LED_MOOD;
                System.out.println("[SERVER] LED 제어: MOOD");
                break;
            case "on":
                packet = LED_ON;
                System.out.println("[SERVER] LED 제어: ON");
                break;
            default:
                System.out.println("[SERVER] 알 수 없는 LED 모드: " + mode);
                return;
        }

        int written = serialPort.writeBytes(packet, packet.length);
        System.out.println("[SERVER] LED 제어 패킷 전송, bytes=" + written);
    }

    // ====== 유틸리티: 브로드캐스트, 헥스 변환 ======
    /** WebSocket 연결 전부에 메시지 전송 (이름을 broadcastToClients로 바꿔서 WebSocketServer.broadcast와 충돌 회피) */
    private void broadcastToClients(String message) {
        System.out.println("[WS] -> " + message);
        synchronized (connections) {
            for (WebSocket ws : connections) {
                if (ws != null && ws.isOpen()) {
                    ws.send(message);
                }
            }
        }
    }

    private static byte[] hexStringToBytes(String s) {
        int len = s.length();
        if (len % 2 != 0) {
            throw new IllegalArgumentException("hex 문자열 길이는 짝수여야 합니다: " + s);
        }
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            data[i / 2] = (byte) Integer.parseInt(s.substring(i, i + 2), 16);
        }
        return data;
    }

    private static String toHexWithCommas(byte[] buf, int len) {
        StringBuilder sb = new StringBuilder(len * 3);
        for (int i = 0; i < len; i++) {
            if (i > 0) sb.append(',');
            sb.append(String.format("%02x", buf[i] & 0xFF));
        }
        return sb.toString();
    }

    // ====== main ======
    public static void main(String[] args) {
        // 시리얼 포트 이름 인자: 예) "COM5" 또는 "/dev/ttyUSB0"
        String portName = args.length > 0 ? args[0] : "COM5";

        InetSocketAddress addr = new InetSocketAddress("0.0.0.0", 52273);
        Anygrow2Server server = new Anygrow2Server(addr, portName);

        System.out.println("[SERVER] Anygrow2 Java Server starting...");
        System.out.println("[SERVER] WebSocket: ws://0.0.0.0:52273");
        System.out.println("[SERVER] SerialPort: " + portName);

        server.start();
    }
}
