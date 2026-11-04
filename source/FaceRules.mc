import Toybox.Lang;
import Toybox.Math;

module FaceRules {
    const CLOCK = 0;
    const FINE = 1;
    const COFFEE = 2;
    const WAKE_MS = 10000;
    const FRAME_MS = 250;

    function lineAt(ms as Number, charge as Number) as Number {
        if (ms < 0 || ms >= WAKE_MS || (ms / 2000) % 2 == 1) { return CLOCK; }
        return ms >= 4000 && charge <= 10 ? COFFEE : FINE;
    }

    // Return the center row, or -1 if the disk has set. Check the 6% rim in
    // every flame pose, since their silhouettes do not share one horizon.
    function sunY(charge as Number) as Number {
        if (charge <= Sky.CUTOFF) { return -1; }
        if (charge >= 50) {
            return Math.round(Sky.HALF_Y + (Sky.Y-Sky.HALF_Y) * (charge-50) / 50.0).toNumber();
        }
        var last = Sky.CUTOFF+1;
        return Math.round(Sky.LAST_Y + (Sky.HALF_Y-Sky.LAST_Y) * (charge-last) / (50.0-last)).toNumber();
    }

    function clockLabel(hour as Number, minute as Number, is24 as Boolean) as String {
        if (!is24) {
            hour %= 12;
            if (hour == 0) { hour = 12; }
        }
        return hour.format(is24 ? "%02d" : "%d") + ":" + minute.format("%02d");
    }

    function temperature(celsius as Numeric?, fahrenheit as Boolean) as String {
        if (celsius == null) { return "--°"; }
        var value = fahrenheit ? celsius * 1.8 + 32 : celsius;
        return Math.round(value).toNumber().toString() + "°";
    }

    function isDay(now as Number, hour as Number, rise as Number?, set as Number?) as Boolean {
        if (rise != null && set != null && rise != set) {
            if (rise < set) { return now >= rise && now < set; }
            // At high latitudes sunset may be early on the same civil date.
            return now >= rise || now < set;
        }
        return hour >= 7 && hour < 19;
    }
}
