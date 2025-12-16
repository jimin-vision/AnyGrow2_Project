package com.example.anygrow;

import java.io.*;

public class TimerProfileStore {
    private final File file;

    public TimerProfileStore(String filename) {
        this.file = new File(filename);
    }

    public void save(TimerProfile[] profiles) {
        try (ObjectOutputStream oos = new ObjectOutputStream(new FileOutputStream(file))) {
            oos.writeObject(profiles);
            System.out.println("[TIMER] Profiles saved: " + file.getAbsolutePath());
        } catch (IOException e) {
            System.err.println("[TIMER] Save failed: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public TimerProfile[] loadOrNull() {
        if (!file.exists()) return null;

        try (ObjectInputStream ois = new ObjectInputStream(new FileInputStream(file))) {
            Object obj = ois.readObject();
            if (obj instanceof TimerProfile[]) {
                return (TimerProfile[]) obj;
            }
            System.err.println("[TIMER] Unexpected save type: " + obj.getClass());
            return null;
        } catch (Exception e) {
            System.err.println("[TIMER] Load failed: " + e.getMessage());
            e.printStackTrace();
            return null;
        }
    }
}
