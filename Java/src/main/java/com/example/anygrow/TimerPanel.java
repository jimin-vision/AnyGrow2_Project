package com.example.anygrow;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.canvas.Canvas;
import javafx.scene.canvas.GraphicsContext;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.util.StringConverter;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

public class TimerPanel extends VBox {

    private final TimerProfileStore store;
    private final TimerProfile[] profiles = new TimerProfile[5];
    private TimerProfile activeProfile;

    private final ComboBox<Integer> comboSlot = new ComboBox<>();
    private final TextField txtName = new TextField();
    private final CheckBox chkEnabled = new CheckBox("타이머 사용");
    private final Label lblActive = new Label("활성 프로필: (없음)");

    private final TextField[] segStart = new TextField[TimerProfile.MAX_SEGMENTS];
    private final TextField[] segEnd   = new TextField[TimerProfile.MAX_SEGMENTS];
    private final ComboBox<String>[] segMode = new ComboBox[TimerProfile.MAX_SEGMENTS];

    private final Canvas timeline = new Canvas(650, 60);

    private final DateTimeFormatter fmt = DateTimeFormatter.ofPattern("HH:mm");

    public TimerPanel(TimerProfileStore store) {
        this.store = store;

        setPadding(new Insets(10));
        setSpacing(8);
        setStyle("-fx-border-color: #cccccc; -fx-border-radius: 4; -fx-border-width: 1;");

        Label title = new Label("LED 타이머 (시간 구간/프로필)");
        title.setStyle("-fx-font-weight: bold;");

        HBox profileRow = buildProfileRow();
        VBox segmentsBox = buildSegmentsBox();

        getChildren().addAll(
                title,
                profileRow,
                segmentsBox,
                chkEnabled,
                new Label("24시간 타임라인 (꺼짐=회색, 켜짐=초록, 무드=파랑):"),
                timeline,
                lblActive
        );

        loadAllFromDisk();
        redrawTimeline();
    }

    // =========================
    // public API
    // =========================
    public TimerProfile getActiveProfile() {
        return activeProfile;
    }

    /** 현재 시간 기준으로 원하는 LED 모드 반환 ("Off" / "On" / "Mood") */
    public String desiredMode(LocalTime now) {
        TimerProfile p = activeProfile;
        if (p == null || !p.enabled) return "Off";

        for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
            TimerSegment seg = p.segments[i];
            if (seg == null) continue;
            if (isWithin(now, seg.start, seg.end)) return seg.mode; // "On" or "Mood"
        }
        return "Off";
    }

    // =========================
    // UI build
    // =========================
    private HBox buildProfileRow() {
        HBox row = new HBox(10);
        row.setAlignment(Pos.CENTER_LEFT);

        for (int i = 1; i <= 5; i++) comboSlot.getItems().add(i);
        comboSlot.setValue(1);

        // 드롭다운에 "번호: 프로필명" 표시
        comboSlot.setConverter(new StringConverter<>() {
            @Override
            public String toString(Integer slot) {
                if (slot == null) return "";
                TimerProfile p = profiles[slot - 1];
                String name = (p != null && p.name != null && !p.name.isBlank())
                        ? p.name
                        : ("프로필 " + slot);
                return slot + ": " + name;
            }

            @Override
            public Integer fromString(String s) {
                if (s == null || s.isBlank()) return null;
                int colon = s.indexOf(':');
                String num = (colon >= 0 ? s.substring(0, colon) : s).trim();
                try {
                    return Integer.parseInt(num);
                } catch (Exception e) {
                    return null;
                }
            }
        });

        comboSlot.setCellFactory(cb -> new ListCell<>() {
            @Override
            protected void updateItem(Integer item, boolean empty) {
                super.updateItem(item, empty);
                setText(empty || item == null ? null : comboSlot.getConverter().toString(item));
            }
        });

        comboSlot.setButtonCell(new ListCell<>() {
            @Override
            protected void updateItem(Integer item, boolean empty) {
                super.updateItem(item, empty);
                setText(empty || item == null ? null : comboSlot.getConverter().toString(item));
            }
        });

        txtName.setPromptText("프로필 이름");
        HBox.setHgrow(txtName, Priority.ALWAYS);

        Button btnLoad = new Button("불러오기");
        Button btnSave = new Button("저장");
        btnLoad.setOnAction(e -> loadProfile());
        btnSave.setOnAction(e -> saveProfile());

        row.getChildren().addAll(
                new Label("프로필 #"),
                comboSlot,
                new Label("이름:"),
                txtName,
                btnLoad,
                btnSave
        );
        return row;
    }

    private VBox buildSegmentsBox() {
        VBox box = new VBox(6);
        box.setPadding(new Insets(4, 0, 4, 0));
        box.getChildren().add(new Label("구간 설정 (구간 안에서는 켜짐/무드, 구간 밖은 꺼짐):"));

        for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
            HBox row = new HBox(8);
            row.setAlignment(Pos.CENTER_LEFT);

            segStart[i] = new TextField();
            segStart[i].setPromptText("HH:mm");
            segStart[i].setPrefWidth(70);

            segEnd[i] = new TextField();
            segEnd[i].setPromptText("HH:mm");
            segEnd[i].setPrefWidth(70);

            segMode[i] = new ComboBox<>();
            // 서버로 보내는 값은 "On"/"Mood"가 필요해서 값 자체는 영어 유지
            segMode[i].getItems().addAll("On", "Mood");
            segMode[i].setPrefWidth(90);

            // 표시만 한국어로 보이게 (값은 "On"/"Mood" 유지)
            segMode[i].setConverter(new StringConverter<>() {
                @Override
                public String toString(String value) {
                    if (value == null) return "";
                    return "On".equals(value) ? "켜짐" : "무드";
                }

                @Override
                public String fromString(String string) {
                    if (string == null) return null;
                    String s = string.trim();
                    if (s.equals("켜짐")) return "On";
                    if (s.equals("무드")) return "Mood";
                    return s;
                }
            });

            // ★ 중요: i 캡처 문제 방지 위해 segMode[i]를 내부에서 참조하지 않고 item 직접 매핑
            segMode[i].setCellFactory(cb -> new ListCell<>() {
                @Override
                protected void updateItem(String item, boolean empty) {
                    super.updateItem(item, empty);
                    if (empty || item == null) {
                        setText(null);
                    } else {
                        setText("On".equals(item) ? "켜짐" : "무드");
                    }
                }
            });

            segMode[i].setButtonCell(new ListCell<>() {
                @Override
                protected void updateItem(String item, boolean empty) {
                    super.updateItem(item, empty);
                    if (empty || item == null) {
                        setText(null);
                    } else {
                        setText("On".equals(item) ? "켜짐" : "무드");
                    }
                }
            });

            row.getChildren().addAll(
                    new Label("#" + (i + 1)),
                    new Label("시작:"), segStart[i],
                    new Label("종료:"), segEnd[i],
                    new Label("모드:"), segMode[i]
            );
            box.getChildren().add(row);
        }

        return box;
    }

    // =========================
    // actions
    // =========================
    private void saveProfile() {
        Integer slot = comboSlot.getValue();
        if (slot == null) return;
        int idx = slot - 1;

        TimerProfile p = new TimerProfile();
        String inputName = (txtName.getText() == null) ? "" : txtName.getText().trim();
        p.name = inputName.isBlank() ? ("프로필 " + slot) : inputName;
        p.enabled = chkEnabled.isSelected();

        try {
            for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
                String s = segStart[i].getText().trim();
                String e = segEnd[i].getText().trim();
                String m = segMode[i].getValue(); // "On"/"Mood"

                if (s.isEmpty() || e.isEmpty() || m == null) {
                    p.segments[i] = null;
                    continue;
                }

                TimerSegment seg = new TimerSegment();
                seg.start = LocalTime.parse(s, fmt).withSecond(0).withNano(0);
                seg.end   = LocalTime.parse(e, fmt).withSecond(0).withNano(0);
                seg.mode  = m;
                p.segments[i] = seg;
            }

        } catch (DateTimeParseException ex) {
            showError("시간 형식이 잘못되었습니다.", "HH:mm 형식으로 입력해주세요. (예: 06:00, 22:00)");
            return;
        }

        profiles[idx] = p;
        activeProfile = p;

        store.save(profiles);
        refreshComboText();
        redrawTimeline();
        lblActive.setText("활성 프로필: #" + slot + " - " + p.name + " (사용=" + p.enabled + ")");

        showInfo("저장 완료", "프로필 #" + slot + " 이(가) 저장되었습니다.");
    }

    private void loadProfile() {
        Integer slot = comboSlot.getValue();
        if (slot == null) return;
        int idx = slot - 1;

        TimerProfile p = profiles[idx];
        if (p == null) {
            showInfo("저장된 프로필이 없습니다.", "프로필 #" + slot + " 은(는) 비어 있습니다.");
            return;
        }

        txtName.setText(p.name);
        chkEnabled.setSelected(p.enabled);

        for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
            TimerSegment seg = p.segments[i];
            if (seg == null) {
                segStart[i].setText("");
                segEnd[i].setText("");
                segMode[i].setValue(null);
            } else {
                segStart[i].setText(seg.start.format(fmt));
                segEnd[i].setText(seg.end.format(fmt));
                segMode[i].setValue(seg.mode); // "On"/"Mood"
            }
        }

        activeProfile = p;
        refreshComboText();
        redrawTimeline();
        lblActive.setText("활성 프로필: #" + slot + " - " + p.name + " (사용=" + p.enabled + ")");

        showInfo("불러오기 완료", "프로필 #" + slot + " 을(를) 불러왔습니다.");
    }

    private void loadAllFromDisk() {
        TimerProfile[] loaded = store.loadOrNull();
        if (loaded == null) return;

        for (int i = 0; i < profiles.length && i < loaded.length; i++) {
            profiles[i] = loaded[i];
        }

        // enabled 우선, 없으면 첫 non-null
        int activeIdx = -1;
        for (int i = 0; i < profiles.length; i++) {
            if (profiles[i] != null && profiles[i].enabled) {
                activeIdx = i;
                break;
            }
        }
        if (activeIdx == -1) {
            for (int i = 0; i < profiles.length; i++) {
                if (profiles[i] != null) {
                    activeIdx = i;
                    break;
                }
            }
        }

        if (activeIdx != -1) {
            activeProfile = profiles[activeIdx];
            int slot = activeIdx + 1;

            comboSlot.setValue(slot);
            txtName.setText(activeProfile.name);
            chkEnabled.setSelected(activeProfile.enabled);

            for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
                TimerSegment seg = activeProfile.segments[i];
                if (seg == null) {
                    segStart[i].setText("");
                    segEnd[i].setText("");
                    segMode[i].setValue(null);
                } else {
                    segStart[i].setText(seg.start.format(fmt));
                    segEnd[i].setText(seg.end.format(fmt));
                    segMode[i].setValue(seg.mode);
                }
            }

            lblActive.setText("활성 프로필: #" + slot + " - " + activeProfile.name + " (사용=" + activeProfile.enabled + ")");
            refreshComboText();
        }
    }

    // =========================
    // timeline
    // =========================
    private void redrawTimeline() {
        GraphicsContext g = timeline.getGraphicsContext2D();
        double w = timeline.getWidth();
        double h = timeline.getHeight();

        g.setFill(Color.WHITE);
        g.fillRect(0, 0, w, h);

        double margin = 30;
        double barX = margin;
        double barY = h / 3.0;
        double barW = w - 2 * margin;
        double barH = h / 3.0;

        // 기본 꺼짐
        g.setFill(Color.LIGHTGRAY);
        g.fillRoundRect(barX, barY, barW, barH, 10, 10);

        TimerProfile p = activeProfile;
        if (p != null) {
            for (int i = 0; i < TimerProfile.MAX_SEGMENTS; i++) {
                TimerSegment seg = p.segments[i];
                if (seg == null) continue;

                double startRatio = seg.start.toSecondOfDay() / (24.0 * 3600.0);
                double endRatio   = seg.end.toSecondOfDay() / (24.0 * 3600.0);

                Color color = "On".equals(seg.mode) ? Color.LIGHTGREEN : Color.LIGHTBLUE;
                g.setFill(color);

                if (startRatio == endRatio) {
                    // 하루 전체
                    g.fillRoundRect(barX, barY, barW, barH, 10, 10);
                } else if (startRatio < endRatio) {
                    // 같은 날 구간
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

        // 시간 눈금
        g.setFill(Color.BLACK);
        g.fillText("0시", barX - 15, barY + barH + 18);
        g.fillText("12시", barX + barW / 2 - 15, barY + barH + 18);
        g.fillText("24시", barX + barW - 15, barY + barH + 18);
    }

    // =========================
    // helpers
    // =========================
    private boolean isWithin(LocalTime now, LocalTime start, LocalTime end) {
        if (start.equals(end)) return true; // 하루 전체
        if (start.isBefore(end)) return !now.isBefore(start) && now.isBefore(end);
        return !now.isBefore(start) || now.isBefore(end); // 자정 넘어감
    }

    private void refreshComboText() {
        Integer cur = comboSlot.getValue();
        comboSlot.setValue(null);
        comboSlot.setValue(cur);
    }

    private void showInfo(String header, String content) {
        Alert a = new Alert(Alert.AlertType.INFORMATION);
        a.setTitle("타이머");
        a.setHeaderText(header);
        a.setContentText(content);
        a.showAndWait();
    }

    private void showError(String header, String content) {
        Alert a = new Alert(Alert.AlertType.ERROR);
        a.setTitle("타이머 오류");
        a.setHeaderText(header);
        a.setContentText(content);
        a.showAndWait();
    }
}
