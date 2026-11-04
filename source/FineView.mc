import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Timer;
import Toybox.WatchUi;

class FineView extends WatchUi.WatchFace {
    private var _data as FaceData;
    private var _scene as FineScene;
    private var _wakeTimer as Timer.Timer?;
    private var _started as Number = 0;
    private var _lastRead as Number = 0;
    private var _readIn as Number = 0;
    private var _visible as Boolean = false;
    private var _shownAt as Number = 0;
    private var _sawSleep as Boolean = false;
    private var _refresh as Boolean = true;

    function initialize() {
        WatchFace.initialize();
        _data = new FaceData();
        _scene = new FineScene();
    }

    function onShow() as Void {
        _visible = true;
        _shownAt = System.getTimer();
        _sawSleep = false;
        _refresh = true;
    }

    function onExitSleep() as Void {
        if (!_visible || _wakeTimer != null) { return; }
        var now = System.getTimer();
        if (!FaceRules.canAnimate(_sawSleep, now-_shownAt)) { return; }
        _sawSleep = false;
        _refresh = true;
        _started = now;
        _wakeTimer = new Timer.Timer();
        _wakeTimer.start(method(:tick), FaceRules.FRAME_MS, true);
        WatchUi.requestUpdate();
    }

    function tick() as Void {
        if (_wakeTimer == null || !_visible) { return; }
        if (System.getTimer()-_started >= FaceRules.WAKE_MS) { stopWake(); }
        WatchUi.requestUpdate();
    }

    private function stopWake() as Void {
        if (_wakeTimer != null) {
            _wakeTimer.stop();
            _wakeTimer = null;
        }
        _scene.rest();
    }

    function onEnterSleep() as Void {
        stopWake();
        _sawSleep = _visible;
        _refresh = true;
        if (_visible) { WatchUi.requestUpdate(); }
    }

    function onHide() as Void {
        _visible = false;
        _sawSleep = false;
        stopWake();
        _scene.release();
    }

    function onUpdate(dc as Dc) as Void {
        var now = System.getTimer();
        // Garmin schedules regular low-power updates at the top of the minute.
        var due = _wakeTimer == null ? Time.now().value()/60 != _data.minuteId : now-_lastRead >= _readIn;
        if (_refresh || due) {
            _readIn = _data.refresh();
            _lastRead = now;
            _refresh = false;
        }
        var elapsed = _wakeTimer == null ? -1 : now-_started;
        if (elapsed >= FaceRules.WAKE_MS) { stopWake(); elapsed = -1; }
        var pose = elapsed < 0 ? 0 : (elapsed / FaceRules.FRAME_MS) % 4;
        _scene.draw(dc, _data, pose, FaceRules.lineAt(elapsed, _data.charge));
    }
}
