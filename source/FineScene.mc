import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

class FineScene {
    // Three still tiles, then left fire, right fire and foreground mask per pose.
    private const DAY = [
        Rez.Drawables.DayTop, Rez.Drawables.DayWall, Rez.Drawables.DayFloor,
        Rez.Drawables.DayLeft0, Rez.Drawables.DayRight0, Rez.Drawables.DayFore0,
        Rez.Drawables.DayLeft1, Rez.Drawables.DayRight1, Rez.Drawables.DayFore1,
        Rez.Drawables.DayLeft2, Rez.Drawables.DayRight2, Rez.Drawables.DayFore2,
        Rez.Drawables.DayLeft3, Rez.Drawables.DayRight3, Rez.Drawables.DayFore3
    ];
    private const NIGHT = [
        Rez.Drawables.NightTop, Rez.Drawables.NightWall, Rez.Drawables.NightFloor,
        Rez.Drawables.NightLeft0, Rez.Drawables.NightRight0, Rez.Drawables.NightFore0,
        Rez.Drawables.NightLeft1, Rez.Drawables.NightRight1, Rez.Drawables.NightFore1,
        Rez.Drawables.NightLeft2, Rez.Drawables.NightRight2, Rez.Drawables.NightFore2,
        Rez.Drawables.NightLeft3, Rez.Drawables.NightRight3, Rez.Drawables.NightFore3
    ];
    private const MARKS = [Rez.Drawables.ThisIsFine, Rez.Drawables.SendCoffee, Rez.Drawables.Alarm,
        Rez.Drawables.Receiver, Rez.Drawables.ReceiverOff, Rez.Drawables.Sun];
    private const FONTS = [Rez.Fonts.ClockWide, Rez.Fonts.ClockCompact, Rez.Fonts.WeatherSmall];
    private var _night as Boolean = false;
    private var _tiles as Array<BitmapResource?> = new [15] as Array<BitmapResource?>;
    private var _marks as Array<BitmapResource?> = new [6] as Array<BitmapResource?>;
    private var _fonts as Array<FontResource?> = new [3] as Array<FontResource?>;

    function rest() as Void {
        for (var i=6; i<_tiles.size(); i+=1) { _tiles[i] = null; }
    }

    function release() as Void {
        for (var i=0; i<_tiles.size(); i+=1) { _tiles[i] = null; }
        for (var j=0; j<_marks.size(); j+=1) { _marks[j] = null; }
        for (var k=0; k<_fonts.size(); k+=1) { _fonts[k] = null; }
    }

    private function tile(i as Number) as BitmapResource {
        var pic = _tiles[i];
        if (pic == null) {
            pic = WatchUi.loadResource(_night ? NIGHT[i] : DAY[i]) as BitmapResource;
            _tiles[i] = pic;
        }
        return pic;
    }

    private function mark(i as Number) as BitmapResource {
        var pic = _marks[i];
        if (pic == null) {
            pic = WatchUi.loadResource(MARKS[i]) as BitmapResource;
            _marks[i] = pic;
        }
        return pic;
    }

    private function font(i as Number) as FontResource {
        var f = _fonts[i];
        if (f == null) {
            f = WatchUi.loadResource(FONTS[i]) as FontResource;
            _fonts[i] = f;
        }
        return f;
    }

    function draw(dc as Dc, data as FaceData, pose as Number, line as Number) as Void {
        if (data.night != _night) {
            for (var i=0; i<_tiles.size(); i+=1) { _tiles[i] = null; }
            _night = data.night;
        }
        var slot = 3+3*pose;
        // A regular onUpdate can invalidate the whole display. These five
        // non-overlapping tiles cover it without allocating a framebuffer.
        dc.drawBitmap(0, 0, tile(0));
        dc.drawBitmap(104, 42, tile(1));
        dc.drawBitmap(0, 155, tile(2));
        dc.drawBitmap(0, 42, tile(slot));
        dc.drawBitmap(188, 42, tile(slot+1));
        drawSky(dc, data.charge, slot+2);
        if (line == FaceRules.CLOCK) {
            drawClock(dc, data);
        } else {
            var label = mark(line == FaceRules.COFFEE ? 1 : 0);
            dc.drawBitmap(130-label.getWidth()/2, 55-label.getHeight()/2, label);
        }
    }

    private function drawSky(dc as Dc, charge as Number, fg as Number) as Void {
        if (!_night) {
            var y = FaceRules.sunY(charge);
            if (y < 0) { return; }
            dc.drawBitmap(Sky.X-Sky.SUN_PAD, y-Sky.SUN_PAD, mark(5));
        } else {
            dc.setColor(0xAAAAFF, Graphics.COLOR_TRANSPARENT);
            dc.fillRectangle(53,100,2,2); dc.fillRectangle(91,99,2,2); dc.fillRectangle(56,111,2,2);
            if (charge <= 0) { return; }
            dc.setColor(0xFFFFAA, Graphics.COLOR_TRANSPARENT);
            for (var i=0; i<Sky.HALF_WIDTHS.size(); i+=1) {
                var edge = Sky.HALF_WIDTHS[i];
                var w = (2*edge*charge+50)/100;
                // Retain one central pixel for a nearly empty crescent.
                if (w == 0 && (i == 8 || i == 9)) { w = 1; }
                if (w > 0) { dc.fillRectangle(Sky.X-edge, Sky.Y-Sky.MOON_R+i, w, 1); }
            }
        }
        // Only the window is transparent. The active fire silhouette always
        // occludes the celestial mark, including on the four animated poses.
        dc.drawBitmap(61,94,tile(fg));
    }

    private function drawClock(dc as Dc, data as FaceData) as Void {
        var compact = data.clock.length() == 5;
        var align = Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER;
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
        dc.drawText(compact ? 115 : 116, 55, font(compact ? 1 : 0), data.clock, align);
        dc.drawText(178, 45, font(2), data.weather, align);
        if (data.alarm) { dc.drawBitmap(163, 54, mark(2)); }
        dc.drawBitmap(data.alarm ? 180 : 171, 54, mark(data.phone ? 3 : 4));
    }
}
