package com.example.anygrow;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.List;

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
        StringBuilder sb = new StringBuilder();
        sb.append("{\"count\":").append(list.size()).append(",\"data\":[");
        for (int i = 0; i < list.size(); i++) {
            var r = list.get(i);
            if (i > 0) sb.append(',');
            sb.append("{")
              .append("\"tsMillis\":").append(r.tsMillis).append(',')
              .append("\"tsText\":\"").append(escapeJson(r.tsText)).append("\",")
              .append("\"temperature\":").append(r.temperature).append(',')
              .append("\"humidity\":").append(r.humidity).append(',')
              .append("\"co2\":").append(r.co2).append(',')
              .append("\"illumination\":").append(r.illumination)
              .append("}");
        }
        sb.append("]}");
        return sb.toString();
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static int parseQueryInt(String query, String key, int def) {
        if (query == null || query.isBlank()) return def;
        String[] parts = query.split("&");
        for (String p : parts) {
            int eq = p.indexOf('=');
            if (eq <= 0) continue;
            String k = p.substring(0, eq);
            String v = p.substring(eq + 1);
            if (k.equals(key)) {
                try { return Integer.parseInt(v); } catch (Exception ignored) { return def; }
            }
        }
        return def;
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
