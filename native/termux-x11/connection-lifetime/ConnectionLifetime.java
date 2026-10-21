package com.termux.x11.utils;

import android.os.IBinder;
import android.os.RemoteException;
import java.util.IdentityHashMap;
import java.util.NoSuchElementException;

/** One death registration per Activity, released on replacement and destruction. */
public final class ConnectionLifetime {
    private static final IdentityHashMap<Object, Entry> entries = new IdentityHashMap<>();

    private ConnectionLifetime() {}

    public static synchronized void link(Object owner, IBinder binder,
                                         IBinder.DeathRecipient callback, int flags)
            throws RemoteException {
        Entry previous = entries.get(owner);
        if (previous != null && previous.binder == binder) return;
        release(owner);
        Entry next = new Entry(owner, binder, callback, flags);
        entries.put(owner, next);
        try {
            binder.linkToDeath(next, flags);
        } catch (RemoteException | RuntimeException failure) {
            if (entries.get(owner) == next) entries.remove(owner);
            throw failure;
        }
    }

    public static synchronized void release(Object owner) {
        Entry entry = entries.remove(owner);
        if (entry != null) {
            try {
                entry.binder.unlinkToDeath(entry, entry.flags);
            } catch (NoSuchElementException ignored) {
                // Binder death already removed the native registration.
            }
        }
    }

    private static final class Entry implements IBinder.DeathRecipient {
        final Object owner;
        final IBinder binder;
        final IBinder.DeathRecipient callback;
        final int flags;

        Entry(Object owner, IBinder binder, IBinder.DeathRecipient callback, int flags) {
            this.owner = owner;
            this.binder = binder;
            this.callback = callback;
            this.flags = flags;
        }

        @Override public void binderDied() {
            synchronized (ConnectionLifetime.class) {
                if (entries.get(owner) != this) return;
                entries.remove(owner);
                // Serialize against replacement so a stale death cannot clear a new connection.
                callback.binderDied();
            }
        }
    }
}
