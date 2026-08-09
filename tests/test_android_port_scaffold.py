import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


class AndroidPortScaffoldTest(unittest.TestCase):
    def test_android_native_host_embeds_existing_game_module(self):
        source = (ROOT / "src/platform/android/CAndroidMain.cpp").read_text(encoding="utf-8")
        self.assertIn('PyImport_AppendInittab("_game", &PyInit__game)', source)
        self.assertIn('CResourcesProvider::configurePlatformRoots(runtimeRoot.string(), writableRoot.string())', source)
        self.assertIn('PyImport_ImportModule("game")', source)
        self.assertIn('PyObject_CallMethod(gameModule, "new", nullptr)', source)
        self.assertIn('filesRoot / "runtime"', source)
        self.assertIn('filesRoot / "user"', source)
        self.assertIn('filesRoot / "python"', source)

    def test_android_cmake_builds_monolithic_sdl_main_without_duplicate_module_entry(self):
        cmake = (ROOT / "android/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('add_library(main SHARED ${GAME_ANDROID_SRC})', cmake)
        self.assertIn('src/core/CModuleEntry\\\\.cpp$', cmake)
        self.assertIn('game_android_python', cmake)
        self.assertIn('pybind11::headers', cmake)
        self.assertIn('${SDL2_ANDROID_LIBS}', cmake)
        self.assertIn('${SDL2_IMAGE_ANDROID_LIBS}', cmake)
        self.assertIn('${SDL2_TTF_ANDROID_LIBS}', cmake)

    def test_gradle_stages_game_and_cpython_payloads(self):
        gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('File(repositoryRoot, "res")', gradle)
        self.assertIn('File(repositoryRoot, "quest_state.py")', gradle)
        self.assertIn('into("python/lib/${pythonStdlibDir.name}")', gradle)
        self.assertIn('File(repositoryRoot, "android/CMakeLists.txt")', gradle)
        self.assertIn('abiFilters += "arm64-v8a"', gradle)

    def test_manifest_launches_sdl_activity_in_landscape(self):
        root = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml").getroot()
        application = root.find("application")
        self.assertIsNotNone(application)
        activities = application.findall("activity")
        self.assertEqual(1, len(activities))
        activity = activities[0]
        self.assertEqual(".FallOfNouraajdActivity", activity.attrib[ANDROID_NS + "name"])
        self.assertEqual("landscape", activity.attrib[ANDROID_NS + "screenOrientation"])
        self.assertEqual("true", activity.attrib[ANDROID_NS + "exported"])

    def test_android_native_plugins_keep_manifest_ids(self):
        manifest = (ROOT / "res/plugins/manifest.json").read_text(encoding="utf-8")
        runtime = (ROOT / "src/plugin/CNativePluginRuntime.cpp").read_text(encoding="utf-8")
        self.assertIn('"library": "plugins/native/native_marker_plugin"', manifest)
        self.assertIn('"library": "plugins/native/native_gameplay"', manifest)
        self.assertIn('library == "plugins/native/native_marker_plugin"', runtime)
        self.assertIn('library == "plugins/native/native_gameplay"', runtime)
        self.assertIn("native_plugin::register_dynamic_marker", runtime)
        self.assertIn("native_plugin::register_gameplay_types", runtime)

    def test_platform_resource_roots_are_explicit_and_reversible(self):
        header = (ROOT / "src/core/CProvider.h").read_text(encoding="utf-8")
        source = (ROOT / "src/core/CPlatformResources.cpp").read_text(encoding="utf-8")
        self.assertIn("configurePlatformRoots", header)
        self.assertIn("clearPlatformRoots", header)
        self.assertIn("searchPath.push_front(*packaged)", source)
        self.assertIn("searchPath.push_front(*writable)", source)
        self.assertLess(source.index("searchPath.push_front(*packaged)"), source.index("searchPath.push_front(*writable)"))


if __name__ == "__main__":
    unittest.main()
