import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Test;

(:test)
function renderClockAndWakeFrames(logger as Test.Logger) as Boolean {
    // Use the target's real resource loader. The compiler accepts compressed
    // status icons that this device rejects on the very first clock draw.
    // Cover the clock and indicators using the native palette. A second full
    // framebuffer would take memory that the watch normally gives to the face.
    var bitmap = new Graphics.BufferedBitmap({ :width => 208, :height => 70 });
    var dc = bitmap.getDc();
    var scene = new FineScene();
    var data = new FaceData();
    data.weather = "64°";
    data.charge = 10;

    for (var theme = 0; theme < 2; theme += 1) {
        data.night = (theme == 1);
        data.clock = data.night ? "22:03" : "8:08";
        data.alarm = true;
        data.phone = true;
        scene.draw(dc, data, 0, FaceRules.CLOCK);

        data.alarm = false;
        data.phone = false;
        scene.draw(dc, data, 0, FaceRules.CLOCK);
        for (var pose = 0; pose < 4; pose += 1) {
            scene.draw(dc, data, pose, FaceRules.FINE);
            scene.draw(dc, data, pose, FaceRules.COFFEE);
        }
        scene.rest();
        scene.draw(dc, data, 0, FaceRules.CLOCK);
    }
    scene.release();
    return true;
}
