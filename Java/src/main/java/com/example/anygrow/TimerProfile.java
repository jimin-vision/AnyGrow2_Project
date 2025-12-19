package com.example.anygrow;

import java.io.Serializable;

public class TimerProfile implements Serializable {
    private static final long serialVersionUID = 1L;

    public static final int MAX_SEGMENTS = 3;

    public String name;
    public TimerSegment[] segments = new TimerSegment[MAX_SEGMENTS];
    public boolean enabled;
}
