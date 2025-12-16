package com.example.anygrow;

import java.sql.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/**
 * 센서 데이터를 SQLite DB에 저장/조회하는 클래스.
 *
 * DB 파일: anygrow2_sensor.db (실행 디렉터리 기준)
 * 테이블: sensor_data
 *
 * 컬럼:
 *  - id           : PK
 *  - ts_millis    : long (epoch milli)
 *  - ts_text      : 사람이 보기 좋은 timestamp (YYYY-MM-DDTHH:MM:SS)
 *  - temperature  : REAL
 *  - humidity     : REAL
 *  - co2          : REAL
 *  - illumination : REAL
 */
public class SensorDataRepository {

    private static final SensorDataRepository INSTANCE = new SensorDataRepository();
    private Connection connection;

    private SensorDataRepository() {
        try {
            // SQLite JDBC 드라이버 로딩
            Class.forName("org.sqlite.JDBC");
            // 프로젝트 실행 폴더에 anygrow2_sensor.db 생성
            connection = DriverManager.getConnection("jdbc:sqlite:anygrow2_sensor.db");
            initSchema();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static SensorDataRepository getInstance() {
        return INSTANCE;
    }

    /** 테이블이 없으면 생성 + 인덱스 생성 */
    private void initSchema() throws SQLException {
        try (Statement st = connection.createStatement()) {
            st.executeUpdate(
                    "CREATE TABLE IF NOT EXISTS sensor_data (" +
                            "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                            "ts_millis INTEGER NOT NULL," +
                            "ts_text TEXT NOT NULL," +
                            "temperature REAL," +
                            "humidity REAL," +
                            "co2 REAL," +
                            "illumination REAL" +
                            ")"
            );
            st.executeUpdate(
                    "CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_data(ts_millis)"
            );
        }
    }

    /**
     * 센서 값 한 세트를 DB에 저장한다.
     * 저장 이후 24시간이 지난 데이터는 자동으로 삭제.
     */
    public synchronized void saveReading(double temp,
                                         double hum,
                                         double co2,
                                         double illum) {
        long now = System.currentTimeMillis();
        LocalDateTime ldt = LocalDateTime.ofInstant(Instant.ofEpochMilli(now), ZoneId.systemDefault());
        String tsText = ldt.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);

        String sql = "INSERT INTO sensor_data(ts_millis, ts_text, temperature, humidity, co2, illumination)" +
                " VALUES (?,?,?,?,?,?)";
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setLong(1, now);
            ps.setString(2, tsText);
            ps.setDouble(3, temp);
            ps.setDouble(4, hum);
            ps.setDouble(5, co2);
            ps.setDouble(6, illum);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }

        deleteOlderThanHours(168); // 7일치 데이터 보관
    }
    // 7일(168시간) 지난 데이터 삭제
    private synchronized void deleteOlderThanHours(int hours) {
        long cutoff = System.currentTimeMillis() - hours * 3600_000L;
        String sql = "DELETE FROM sensor_data WHERE ts_millis < ?";
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setLong(1, cutoff);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    // ================== 아래는 예시 조회용 ==================

    public static class SensorReading {
        public final long tsMillis;
        public final String tsText;
        public final double temperature;
        public final double humidity;
        public final double co2;
        public final double illumination;

        public SensorReading(long tsMillis, String tsText,
                             double temperature, double humidity,
                             double co2, double illumination) {
            this.tsMillis = tsMillis;
            this.tsText = tsText;
            this.temperature = temperature;
            this.humidity = humidity;
            this.co2 = co2;
            this.illumination = illumination;
        }
    }

    /** 최근 24시간 데이터 조회 예시 메서드 */
    public synchronized List<SensorReading> findLast24Hours() {
        long cutoff = System.currentTimeMillis() - 24L * 3600_000L;
        String sql = "SELECT ts_millis, ts_text, temperature, humidity, co2, illumination" +
                " FROM sensor_data WHERE ts_millis >= ? ORDER BY ts_millis ASC";
        List<SensorReading> result = new ArrayList<>();
        try (PreparedStatement ps = connection.prepareStatement(sql)) {
            ps.setLong(1, cutoff);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    long tsMillis = rs.getLong("ts_millis");
                    String tsText = rs.getString("ts_text");
                    double temp = rs.getDouble("temperature");
                    double hum = rs.getDouble("humidity");
                    double co2 = rs.getDouble("co2");
                    double illum = rs.getDouble("illumination");
                    result.add(new SensorReading(tsMillis, tsText, temp, hum, co2, illum));
                }
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return result;
    }

    public synchronized List<SensorReading> findLastHours(int hours, int limit) {
    long cutoff = System.currentTimeMillis() - (long) hours * 3600_000L;
    String sql = "SELECT ts_millis, ts_text, temperature, humidity, co2, illumination " +
            "FROM sensor_data WHERE ts_millis >= ? ORDER BY ts_millis ASC LIMIT ?";
    List<SensorReading> result = new ArrayList<>();
    try (PreparedStatement ps = connection.prepareStatement(sql)) {
        ps.setLong(1, cutoff);
        ps.setInt(2, limit);
        try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                result.add(new SensorReading(
                        rs.getLong("ts_millis"),
                        rs.getString("ts_text"),
                        rs.getDouble("temperature"),
                        rs.getDouble("humidity"),
                        rs.getDouble("co2"),
                        rs.getDouble("illumination")
                ));
            }
        }
    } catch (SQLException e) {
        e.printStackTrace();
    }
    return result;
}
    
}
