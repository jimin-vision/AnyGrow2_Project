package com.example.anygrow;

import java.io.InputStream;
import java.util.Properties;

/**
 * 'config.properties' 파일에서 설정을 로드하는 유틸리티 클래스.
 * 설정 파일을 찾을 수 없거나 값이 없는 경우 기본값을 사용합니다.
 */
public class AppConfig {
    private static final Properties props = new Properties();
    private static final String CONFIG_FILE = "config.properties";

    static {
        try (InputStream input = AppConfig.class.getClassLoader().getResourceAsStream(CONFIG_FILE)) {
            if (input == null) {
                System.err.println("WARNING: Cannot find '" + CONFIG_FILE + "'. Using default settings.");
            } else {
                props.load(input);
                System.out.println("Loaded settings from " + CONFIG_FILE);
            }
        } catch (Exception ex) {
            System.err.println("ERROR: Failed to load " + CONFIG_FILE + ". Using default settings.");
            ex.printStackTrace();
        }
    }

    private static int getInt(String key, int defaultValue) {
        try {
            return Integer.parseInt(props.getProperty(key, String.valueOf(defaultValue)));
        } catch (NumberFormatException e) {
            System.err.println("WARNING: Invalid number format for key '" + key + "'. Using default value: " + defaultValue);
            return defaultValue;
        }
    }

    private static String getString(String key, String defaultValue) {
        return props.getProperty(key, defaultValue);
    }

    // --- Specific Getters ---

    public static int getWebSocketPort() {
        return getInt("server.websocket.port", 52273);
    }

    public static int getHttpPort() {
        return getInt("server.http.port", 8080);
    }

    public static String getSerialPort() {
        return getString("hardware.serial.port", "COM5");
    }

    public static String getDbFilePath() {
        return getString("database.filepath", "anygrow2_sensor.db");
    }

    public static String getTimerProfilesPath() {
        return getString("timer.profiles.filepath", "anygrow2_timer_profiles.dat");
    }
}
