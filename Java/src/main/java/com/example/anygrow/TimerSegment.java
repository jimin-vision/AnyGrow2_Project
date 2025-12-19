package com.example.anygrow;

import java.io.Serializable;
import java.time.LocalTime;

public class TimerSegment implements Serializable {
    private static final long serialVersionUID = 1L;

    public LocalTime start;
    public LocalTime end;
    public String mode; // "On" or "Mood"
}
