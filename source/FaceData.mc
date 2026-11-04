import Toybox.Lang;
import Toybox.Math;
import Toybox.System;
import Toybox.Time;
import Toybox.Weather;

class FaceData {
    var clock as String = "";
    var weather as String = "--°";
    var charge as Number = 100;
    var alarm as Boolean = false;
    var phone as Boolean = false;
    var night as Boolean = false;
    var minuteId as Number = -1;

    private var _lastWeather as Number?;
    private var _solarDay as Number?;
    private var _rise as Number?;
    private var _set as Number?;
    private var _temp as Numeric?;
    private var _observedAt as Number?;

    // Called on display and wake, then at minute boundaries, never by each fire pose.
    function refresh() as Number {
        var now = Time.now();
        var stamp = now.value();
        minuteId = stamp / 60;
        var local = System.getClockTime();
        var settings = System.getDeviceSettings();
        clock = FaceRules.clockLabel(local.hour, local.min, settings.is24Hour);
        charge = Math.round(System.getSystemStats().battery).toNumber();
        alarm = settings.alarmCount > 0;
        phone = settings.phoneConnected;

        var dayStart = Time.today().value();
        if (_lastWeather == null || stamp < _lastWeather || stamp-_lastWeather >= 900 || _solarDay != dayStart) {
            // The weather station provides its location. Never start a GPS fix.
            var conditions = Weather.getCurrentConditions();
            _lastWeather = stamp;
            if (_solarDay != dayStart) { _rise = null; _set = null; }
            _solarDay = dayStart;
            _temp = null; _observedAt = null;
            if (conditions != null) {
                _temp = conditions.temperature;
                var observation = conditions.observationTime;
                if (observation != null) { _observedAt = observation.value(); }
                var location = conditions.observationLocationPosition;
                if (location != null) {
                    var noon = new Time.Moment(dayStart + 43200);
                    var rise = Weather.getSunrise(location, noon);
                    var set = Weather.getSunset(location, noon);
                    _rise = rise != null ? rise.value() : null;
                    _set = set != null ? set.value() : null;
                }
            }
        }
        var stale = _observedAt != null && stamp-_observedAt > 10800;
        weather = FaceRules.temperature(stale ? null : _temp, settings.temperatureUnits == System.UNIT_STATUTE);
        night = !FaceRules.isDay(stamp, local.hour, _rise, _set);
        return (60-local.sec)*1000;
    }
}
