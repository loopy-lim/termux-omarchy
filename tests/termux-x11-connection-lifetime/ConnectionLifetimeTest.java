import android.os.IBinder;
import android.os.RemoteException;
import com.termux.x11.utils.ConnectionLifetime;
import java.util.ArrayList;
import java.util.List;

public final class ConnectionLifetimeTest {
    static final class Binder implements IBinder {
        final List<DeathRecipient> recipients = new ArrayList<>();
        boolean dead;
        int peak;
        public void linkToDeath(DeathRecipient recipient, int flags) throws RemoteException {
            if (dead) throw new RemoteException();
            recipients.add(recipient); peak = Math.max(peak, recipients.size());
        }
        public boolean unlinkToDeath(DeathRecipient recipient, int flags) {
            return recipients.remove(recipient);
        }
        void die() {
            dead = true;
            List<DeathRecipient> pending = new ArrayList<>(recipients);
            recipients.clear();
            for (DeathRecipient recipient : pending) recipient.binderDied();
        }
    }
    static void check(boolean value, String reason) {
        if (!value) throw new AssertionError(reason);
    }
    public static void main(String[] args) throws Exception {
        Object owner = new Object(); Binder binder = new Binder(); int[] deaths = {0};
        boolean legacy = args.length > 0;
        for (int i = 0; i < 60000; i++) {
            IBinder.DeathRecipient recipient = () -> deaths[0]++;
            if (legacy) binder.linkToDeath(recipient, 0);
            else ConnectionLifetime.link(owner, binder, recipient, 0);
        }
        check(binder.peak == 1, "duplicate-broadcast-registration-growth: " + binder.peak);
        IBinder.DeathRecipient stale = binder.recipients.get(0);
        Binder replacement = new Binder();
        ConnectionLifetime.link(owner, replacement, () -> deaths[0]++, 0);
        check(binder.recipients.isEmpty(), "old-binder-not-unlinked");
        stale.binderDied(); check(deaths[0] == 0, "stale-death-cleared-new-connection");
        replacement.die(); check(deaths[0] == 1, "death-not-delivered-once");
        ConnectionLifetime.release(owner);
        try { ConnectionLifetime.link(owner, replacement, () -> deaths[0]++, 0); throw new AssertionError("dead-binder-accepted"); }
        catch (RemoteException expected) { }
        Binder live = new Binder(); Object second = new Object();
        ConnectionLifetime.link(owner, live, () -> deaths[0]++, 0);
        ConnectionLifetime.link(second, live, () -> deaths[0]++, 0);
        ConnectionLifetime.release(owner);
        check(live.recipients.size() == 1, "destroy-unlinked-other-activity");
        ConnectionLifetime.release(second); ConnectionLifetime.release(second);
        check(live.recipients.isEmpty(), "destroy-leaked-registration");
        for (int i = 0; i < 10000; i++) {
            Object activity = new Object();
            ConnectionLifetime.link(activity, live, () -> deaths[0]++, 0);
            ConnectionLifetime.release(activity);
        }
        check(live.recipients.isEmpty(), "activity-churn-leak");
        System.out.println("PASS 60000 duplicate broadcasts, replacement, stale death, dead binder, two activities, 10000 recreations");
    }
}
