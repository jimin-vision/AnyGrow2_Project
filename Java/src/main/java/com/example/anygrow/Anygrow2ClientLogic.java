package com.example.anygrow;

/**
 * anygrow2_client.js 의 센서 데이터 처리/알람 로직을 옮긴 Java 클래스.
 * - 소켓으로부터 들어온 문자열 패킷(data)을 onSerialReceive() 에 넘기면
 *   내부에서 패킷을 누적하다가 "ff,ff" 가 포함된 시점에 한 번 처리합니다.
 */
public class Anygrow2ClientLogic {

    // 수신 패킷 누적 버퍼
    private final StringBuilder packet = new StringBuilder();

    // 패킷 종료 마커
    private static final String ETX = "ff,ff";

    /**
     * arrEnv 구조
     * [0] : 온도
     * [1] : 습도
     * [2] : CO2
     * [3] : 조도
     *
     * [ ][0] : 센서값
     * [ ][1] : 최소값
     * [ ][2] : 최대값
     * [ ][3] : 알람 플래그 (0: 알람 허용, 1: 이미 알람 발생)
     */
    private final double[][] arrEnv = new double[4][4];

    public Anygrow2ClientLogic() {
        // 기본 임계값은 JS 코드의 change_threshold() 를 기반으로 적당히 초기화
        changeThreshold(
                18, 28,   // 온도 min/max
                40, 70,   // 습도 min/max
                400, 1000,// CO2 min/max
                100, 5000 // 조도 min/max
        );
        alarmInit();
    }

    /**
     * JS 의 socket.on('serial_recive', function(data){ ... }) 에 대응.
     * 서버(WebSocket 등)에서 받은 문자열 data 를 그대로 넘겨주면 됩니다.
     */
    public void onSerialReceive(String data) {
        // 패킷이 끊어서 들어올 수 있으므로 누적
        packet.append(data);

        System.out.println("[CLIENT] raw packet: " + packet);

        // ETX("ff,ff") 가 포함되면 한 패킷 처리
        if (packet.indexOf(ETX) >= 0) {
            String fullPacket = packet.toString();
            String[] arrReceiveData = fullPacket.split(",");

            // 정상 패킷 길이 체크
            if (arrReceiveData.length == 30) {
                // MODE 필드(인덱스 1)가 "02" 일 때만 센서값으로 처리
                if ("02".equals(arrReceiveData[1])) {
                    // 온도/습도/CO2/조도 변환
                    arrEnv[0][0] = hex2dec(arrReceiveData, 10, 12) / 10.0; // 온도
                    arrEnv[1][0] = hex2dec(arrReceiveData, 14, 16) / 10.0; // 습도
                    arrEnv[2][0] = hex2dec(arrReceiveData, 18, 21);        // CO2
                    arrEnv[3][0] = hex2dec(arrReceiveData, 23, 26);        // 조도
                }

                // JS 에서는 여기서 차트/DOM 업데이트를 했지만,
                // 예제에선 콘솔 출력 + 알람 체크만 수행
                printCurrentValuesToConsole();
                checkAlarmAll();
            } else {
                System.out.println("[CLIENT] 잘못된 패킷 길이: " + arrReceiveData.length);
            }

            // 다음 패킷 준비
            packet.setLength(0);
        }
    }

    /**
     * anygrow2_client.js 의 hex2dec() 함수 포팅.
     *   result += String(eval(arr[i])-30);
     *   return eval(result);
     *
     * Java 에서는 각 요소를 int 로 파싱 후 30을 빼고,
     * 그 결과들을 이어붙인 문자열을 다시 int 로 변환합니다.
     */
    private int hex2dec(String[] arr, int first, int last) {
        StringBuilder result = new StringBuilder();
        for (int i = first; i <= last; i++) {
            String item = arr[i].trim();
            if (item.isEmpty()) {
                continue;
            }
            try {
                int v = Integer.parseInt(item); // "0".."9" 를 가정
                v = v - 30;
                result.append(v);
            } catch (NumberFormatException e) {
                // JS 의 eval 이 실패하면 NaN 이 되지만,
                // 여기서는 단순히 0 으로 취급
                result.append("0");
            }
        }
        try {
            return Integer.parseInt(result.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /** 알람 한 항목 체크 */
    private void alarm(double valData, double valMin, double valMax, int alarmFlag, String factor) {
        if (alarmFlag != 0) {
            return; // 이미 알람 발생한 상태
        }
        if (valData < valMin) {
            String comment = factor + "가 너무 낮습니다";
            System.out.println("[ALARM] " + comment + " (값: " + valData + ")");
        } else if (valData > valMax) {
            String comment = factor + "가 너무 높습니다";
            System.out.println("[ALARM] " + comment + " (값: " + valData + ")");
        }
    }

    /** JS 의 change_threshold() */
    public void changeThreshold(
            double tempMin, double tempMax,
            double humMin, double humMax,
            double co2Min, double co2Max,
            double illumMin, double illumMax
    ) {
        arrEnv[0][1] = tempMin;
        arrEnv[0][2] = tempMax;

        arrEnv[1][1] = humMin;
        arrEnv[1][2] = humMax;

        arrEnv[2][1] = co2Min;
        arrEnv[2][2] = co2Max;

        arrEnv[3][1] = illumMin;
        arrEnv[3][2] = illumMax;
    }

    /** 알람 플래그 초기화 */
    public void alarmInit() {
        arrEnv[0][3] = 0;
        arrEnv[1][3] = 0;
        arrEnv[2][3] = 0;
        arrEnv[3][3] = 0;
    }

    /** 전체 알람 체크 */
    private void checkAlarmAll() {
        alarm(arrEnv[0][0], arrEnv[0][1], arrEnv[0][2], (int) arrEnv[0][3], "온도");
        alarm(arrEnv[1][0], arrEnv[1][1], arrEnv[1][2], (int) arrEnv[1][3], "습도");
        if (arrEnv[2][0] < 6000) { // JS 코드의 CO2 6000 상한
            alarm(arrEnv[2][0], arrEnv[2][1], arrEnv[2][2], (int) arrEnv[2][3], "이산화탄소");
        }
        alarm(arrEnv[3][0], arrEnv[3][1], arrEnv[3][2], (int) arrEnv[3][3], "조도");
    }

    /** 센서값 콘솔 출력 */
    private void printCurrentValuesToConsole() {
        System.out.println("[CLIENT] 현재 센서값");
        System.out.println("  온도: " + arrEnv[0][0]);
        System.out.println("  습도: " + arrEnv[1][0]);
        if (arrEnv[2][0] < 6000) {
            System.out.println("  CO2: " + arrEnv[2][0]);
        }
        System.out.println("  조도: " + arrEnv[3][0]);
    }

    /** 간단 테스트용 main (가짜 패킷) */
    public static void main(String[] args) {
        Anygrow2ClientLogic logic = new Anygrow2ClientLogic();

        // JS 서버에서 보내는 것처럼 쉼표로 구분된 문자열 예시
        String fakePacket =
                "00,02,0,0,0,0,0,0,0,0," +
                "3,3,3," +     // 온도 (10~12)
                "4,4,4," +     // 습도 (14~16)
                "5,5,5,5," +   // CO2  (18~21)
                "6,6,6,6," +   // 조도 (23~26)
                "0,ff,ff";     // 패킷 끝 ETX 포함

        logic.onSerialReceive(fakePacket);
    }

    // Anygrow2ClientLogic.java 제일 아래쪽에 추가

    // --- 센서값 조회용 getter들 ---

    public double getTemperature() {
        return arrEnv[0][0];
    }

    public double getHumidity() {
        return arrEnv[1][0];
    }

    public double getCo2() {
        return arrEnv[2][0];
    }

    public double getIllumination() {
        return arrEnv[3][0];
    }

}
