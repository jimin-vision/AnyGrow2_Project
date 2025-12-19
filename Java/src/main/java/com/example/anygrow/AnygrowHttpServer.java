package com.example.anygrow;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class AnygrowHttpServer {

    private final HttpServer server;

    public AnygrowHttpServer(String bindHost, int port) throws IOException {
        server = HttpServer.create(new InetSocketAddress(bindHost, port), 0);

        // API: 센서 데이터 JSON
        server.createContext("/api/sensors", this::handleSensorsApi);

        // 정적 파일: /web 폴더에서 제공
        server.createContext("/", this::handleStatic);

        server.setExecutor(null);
    }

    public void start() {
        server.start();
        System.out.println("[HTTP] Web UI:  http://0.0.0.0:" + server.getAddress().getPort() + "/");
        System.out.println("[HTTP] API:     http://0.0.0.0:" + server.getAddress().getPort() + "/api/sensors?hours=24&limit=2000");
    }

    public void stop() {
        server.stop(0);
        System.out.println("[HTTP] Web UI server stopped.");
    }

    private void handleSensorsApi(HttpExchange ex) throws IOException {
        if (!"GET".equalsIgnoreCase(ex.getRequestMethod())) {
            sendText(ex, 405, "Method Not Allowed");
            return;
        }

        int hours = parseQueryInt(ex.getRequestURI().getRawQuery(), "hours", 24);
        int limit = parseQueryInt(ex.getRequestURI().getRawQuery(), "limit", 2000);
        if (hours < 1) hours = 1;
        if (hours > 168) hours = 168; // 7일
        if (limit < 1) limit = 1;
        if (limit > 20000) limit = 20000;

        List<SensorDataRepository.SensorReading> list =
                SensorDataRepository.getInstance().findLastHours(hours, limit);

        String json = toJson(list);

        Headers h = ex.getResponseHeaders();
        h.set("Content-Type", "application/json; charset=utf-8");
        h.set("Access-Control-Allow-Origin", "*"); // 원격 조회용 CORS
        sendBytes(ex, 200, json.getBytes(StandardCharsets.UTF_8));
    }

    private void handleStatic(HttpExchange ex) throws IOException {
        String path = ex.getRequestURI().getPath();
        if (path == null || path.isBlank() || "/".equals(path)) path = "/index.html";

        // 리소스: src/main/resources/web/*
        String resourcePath = "web" + path;
        InputStream in = Thread.currentThread().getContextClassLoader().getResourceAsStream(resourcePath);

        if (in == null) {
            sendText(ex, 404, "Not Found: " + path);
            return;
        }

        byte[] bytes = readAllBytes(in);
        String contentType = guessContentType(path);
        ex.getResponseHeaders().set("Content-Type", contentType);
        sendBytes(ex, 200, bytes);
    }

    private static String toJson(List<SensorDataRepository.SensorReading> list) {
        String data = list.stream()
                .map(r -> String.format(
                        "{\"tsMillis\":%d,\"tsText\":\"%s\",\"temperature\":%.1f,\"humidity\":%.1f,\"co2\":%.0f,\"illumination\":%.0f}",
                        r.tsMillis, escapeJson(r.tsText), r.temperature, r.humidity, r.co2, r.illumination
                ))
                .collect(Collectors.joining(","));

        return String.format("{\"count\":%d,\"data\":[%s]}", list.size(), data);
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static int parseQueryInt(String query, String key, int def) {
        if (query == null || query.isBlank()) return def;
        return Arrays.stream(query.split("&"))
                .map(p -> p.split("=", 2))
                .filter(parts -> parts.length == 2 && parts[0].equals(key))
                .findFirst()
                .map(parts -> {
                    try {
                        return Integer.parseInt(parts[1]);
                    } catch (NumberFormatException e) {
                        return def;
                    }
                })
                .orElse(def);
    }

    private static void sendText(HttpExchange ex, int code, String text) throws IOException {
        sendBytes(ex, code, text.getBytes(StandardCharsets.UTF_8));
    }

    private static void sendBytes(HttpExchange ex, int code, byte[] body) throws IOException {
        ex.sendResponseHeaders(code, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }

    private static byte[] readAllBytes(InputStream in) throws IOException {
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) bos.write(buf, 0, n);
            return bos.toByteArray();
        } finally {
            in.close();
        }
    }

    private static String guessContentType(String path) {
        String type = URLConnection.guessContentTypeFromName(path);
        if (type != null) return type;
        if (path.endsWith(".js")) return "application/javascript; charset=utf-8";
        if (path.endsWith(".css")) return "text/css; charset=utf-8";
        if (path.endsWith(".html")) return "text/html; charset=utf-8";
        return "application/octet-stream";
    }
}
