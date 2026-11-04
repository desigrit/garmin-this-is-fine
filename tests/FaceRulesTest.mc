import Toybox.Lang;
import Toybox.Test;

(:test)
function wakeSequence(logger as Test.Logger) as Boolean {
    var times = [-1, 0, 1999, 2000, 3999, 4000, 5999, 6000, 7999, 8000, 9999, 10000, 15000];
    var low = [0, 1, 1, 0, 0, 2, 2, 0, 0, 2, 2, 0, 0];
    var normal = [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0];
    for (var i=0; i<times.size(); i+=1) {
        Test.assertEqual(low[i], FaceRules.lineAt(times[i],10));
        Test.assertEqual(normal[i], FaceRules.lineAt(times[i],11));
    }
    return true;
}

(:test)
function lastSunlight(logger as Test.Logger) as Boolean {
    for (var b=0; b<=5; b+=1) { Test.assertEqual(-1, FaceRules.sunY(b)); }
    Test.assertEqual(142, FaceRules.sunY(6));
    Test.assertEqual(134, FaceRules.sunY(50));
    Test.assertEqual(105, FaceRules.sunY(100));
    for (var p=7; p<=100; p+=1) {
        Test.assert(FaceRules.sunY(p) <= FaceRules.sunY(p-1));
    }
    return true;
}

(:test)
function clockAndWeather(logger as Test.Logger) as Boolean {
    Test.assertEqual("12:04", FaceRules.clockLabel(0,4,false));
    Test.assertEqual("00:04", FaceRules.clockLabel(0,4,true));
    Test.assertEqual("12:00", FaceRules.clockLabel(12,0,false));
    Test.assertEqual("1:09", FaceRules.clockLabel(13,9,false));
    Test.assertEqual("23:59", FaceRules.clockLabel(23,59,true));
    Test.assertEqual("--°", FaceRules.temperature(null,true));
    Test.assertEqual("32°", FaceRules.temperature(0,true));
    Test.assertEqual("-40°", FaceRules.temperature(-40,true));
    Test.assertEqual("-3°", FaceRules.temperature(-3.2,false));
    return true;
}

(:test)
function dayNightEdges(logger as Test.Logger) as Boolean {
    Test.assert(!FaceRules.isDay(99,12,100,200));
    Test.assert(FaceRules.isDay(100,12,100,200));
    Test.assert(!FaceRules.isDay(200,12,100,200));
    Test.assert(FaceRules.isDay(225,12,200,100));
    Test.assert(!FaceRules.isDay(150,12,200,100));
    Test.assert(FaceRules.isDay(10,7,null,null));
    Test.assert(!FaceRules.isDay(10,19,null,null));
    return true;
}
