package com.example.anygrow;

import java.net.URI;
import java.net.URISyntaxException;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

/**
 * anygrow2_client.js 전체 동작을 Java(콘솔)로 재현한 예제.
 *
 * - WebSocket 서버(ws://host:52273)에 접속
 * - 서버에서 보내는 "serial_recive:..." 메시지를 Anygrow2ClientLogic 으로 전달
 * - 패킷이 완성된 경우 서버에 "comm_state:..." 메시지 전송
 * - 필요한 경우 sendSerialWrite() 로 LED 제어 명령(Off / Mood / On) 보낼 수 있음
 */
public class Anygrow2Client extends WebSocketClient {

    private final Anygrow2ClientLogic logic = new Anygrow2ClientLogic();

    public Anygrow2Client(URI serverUri) {
        super(serverUri);
    }

    @Override
    public void onOpen(ServerHandshake handshakedata) {
        System.out.println("[CLIENT-WS] Connected to server.");
    }

    @Override
    public void onMessage(String message) {
        System.out.println("[CLIENT-WS] recv: " + message);

        // 서버에서 보내는 형식 : "serial_recive:0,2,...,ff,ff"
        if (message.startsWith("serial_recive:")) {
            String data = message.substring("serial_recive:".length());
            logic.onSerialReceive(data);

            // 패킷이 끝났는지 간단히 검사(ETX 포함 여부)
            if (data.contains("ff,ff")) {
                // JS 의 socket.emit('comm_state', "sensor data response"); 에 해당
                send("comm_state:sensor data response");
            }
        }
    }

    @Override
    public void onClose(int code, String reason, boolean remote) {
        System.out.println("[CLIENT-WS] Connection closed: code=" + code + " reason=" + reason);
    }

    @Override
    public void onError(Exception ex) {
        System.err.println("[CLIENT-WS] error: " + ex.getMessage());
        ex.printStackTrace();
    }

    /** LED 제어 (Off / Mood / On) */
    public void sendSerialWrite(String mode) {
        String msg = "serial_write:" + mode;
        System.out.println("[CLIENT-WS] send: " + msg);
        send(msg);
    }

    /** 간단 실행용 main */
    public static void main(String[] args) throws URISyntaxException, InterruptedException {
        String serverUri = args.length > 0 ? args[0] : "ws://localhost:" + AppConfig.getWebSocketPort();
        Anygrow2Client client = new Anygrow2Client(new URI(serverUri));
        client.connectBlocking(); // 접속 대기

        // 예: LED OFF → ON → MOOD 로 순차 제어
        client.sendSerialWrite("Off");
        Thread.sleep(2000);
        client.sendSerialWrite("On");
        Thread.sleep(2000);
        client.sendSerialWrite("Mood");
    }
}
