import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = ROOT / "android/app/src/main/java/com/lisu188/fallofnouraajd/RuntimeAssets.java"
JAVA_SOURCES = {
    "android/content/Context.java": """
        package android.content;
        import android.content.pm.PackageManager;
        import android.content.res.AssetManager;
        import java.io.File;
        public final class Context {
            private final File filesDir;
            private final PackageManager manager;
            private final AssetManager assets;
            public Context(File filesDir, PackageManager manager, AssetManager assets) {
                this.filesDir = filesDir;
                this.manager = manager;
                this.assets = assets;
            }
            public File getFilesDir() { return filesDir; }
            public PackageManager getPackageManager() { return manager; }
            public String getPackageName() { return "com.lisu188.fallofnouraajd"; }
            public AssetManager getAssets() { return assets; }
        }
    """,
    "android/content/pm/PackageInfo.java": """
        package android.content.pm;
        public final class PackageInfo {
            public int versionCode = 1;
            public long lastUpdateTime = 100;
            public long getLongVersionCode() { return versionCode; }
        }
    """,
    "android/content/pm/PackageManager.java": """
        package android.content.pm;
        public final class PackageManager {
            private final PackageInfo info;
            public PackageManager(PackageInfo info) { this.info = info; }
            public PackageInfo getPackageInfo(String name, int flags) { return info; }
        }
    """,
    "android/os/Build.java": """
        package android.os;
        public final class Build {
            public static final class VERSION { public static int SDK_INT = 28; }
            public static final class VERSION_CODES { public static final int P = 28; }
        }
    """,
    "android/content/res/AssetManager.java": """
        package android.content.res;
        import java.io.File;
        import java.io.IOException;
        import java.io.InputStream;
        import java.nio.file.Files;
        import java.util.Arrays;
        public final class AssetManager {
            private final File root;
            public int openedFiles;
            public boolean unavailable;
            public String failPath;
            public AssetManager(File root) { this.root = root; }
            public String[] list(String path) throws IOException {
                if (unavailable) { throw new IOException("Unexpected asset access"); }
                File file = new File(root, path);
                String[] children = file.list();
                if (children == null) { return new String[0]; }
                Arrays.sort(children);
                return children;
            }
            public InputStream open(String path) throws IOException {
                if (unavailable || path.equals(failPath)) { throw new IOException("Injected asset read failure"); }
                openedFiles++;
                return Files.newInputStream(new File(root, path).toPath());
            }
        }
    """,
    "com/lisu188/fallofnouraajd/RuntimeAssetsHarness.java": """
        package com.lisu188.fallofnouraajd;
        import android.content.Context;
        import android.content.pm.PackageInfo;
        import android.content.pm.PackageManager;
        import android.content.res.AssetManager;
        import java.io.IOException;
        import java.nio.charset.StandardCharsets;
        import java.nio.file.Files;
        import java.nio.file.Path;
        public final class RuntimeAssetsHarness {
            private static final String GAME = "runtime/config/content.json";
            private static final String PYTHON = "python/lib/python3.14/library.py";
            private static final String SAVE = "user/save/slot.json";
            private static final String MARKER = ".android-runtime-version";
            private static final class Fixture {
                final Path packaged;
                final Path installed;
                final PackageInfo info = new PackageInfo();
                final AssetManager assets;
                final Context context;
                Fixture(Path root) throws IOException {
                    packaged = Files.createDirectories(root.resolve("packaged"));
                    installed = Files.createDirectories(root.resolve("installed"));
                    assets = new AssetManager(packaged.toFile());
                    context = new Context(installed.toFile(), new PackageManager(info), assets);
                    write(packaged.resolve(GAME), "old game");
                    write(packaged.resolve(PYTHON), "old python");
                    write(packaged.resolve("runtime/obsolete.txt"), "obsolete game");
                    write(packaged.resolve("python/lib/python3.14/obsolete.py"), "obsolete python");
                    write(installed.resolve(SAVE), "persistent save");
                }
                void updatePayload() throws IOException {
                    write(packaged.resolve(GAME), "current main game");
                    write(packaged.resolve(PYTHON), "current main python");
                    Files.delete(packaged.resolve("runtime/obsolete.txt"));
                    Files.delete(packaged.resolve("python/lib/python3.14/obsolete.py"));
                }
                void checkUpdatedPayload() throws IOException {
                    require(read(installed.resolve(GAME)).equals("current main game"), "Game payload stayed stale");
                    require(read(installed.resolve(PYTHON)).equals("current main python"),
                            "Python payload stayed stale");
                    require(!Files.exists(installed.resolve("runtime/obsolete.txt")), "Obsolete game file survived");
                    require(!Files.exists(installed.resolve("python/lib/python3.14/obsolete.py")),
                            "Obsolete Python file survived");
                    checkSave();
                }
                void checkSave() throws IOException {
                    require(read(installed.resolve(SAVE)).equals("persistent save"), "Save data changed");
                }
            }
            private static void write(Path path, String value) throws IOException {
                Files.createDirectories(path.getParent());
                Files.write(path, value.getBytes(StandardCharsets.UTF_8));
            }
            private static String read(Path path) throws IOException {
                return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
            }
            private static void require(boolean condition, String message) {
                if (!condition) { throw new AssertionError(message); }
            }
            private static void sameVersionUpdate(Fixture fixture) throws IOException {
                RuntimeAssets.install(fixture.context);
                String oldMarker = read(fixture.installed.resolve(MARKER));
                fixture.updatePayload();
                fixture.info.lastUpdateTime = 200;
                RuntimeAssets.install(fixture.context);
                fixture.checkUpdatedPayload();
                require(!read(fixture.installed.resolve(MARKER)).equals(oldMarker), "Update identity did not change");
            }
            private static void unchangedInstall(Fixture fixture) throws IOException {
                RuntimeAssets.install(fixture.context);
                int openedFiles = fixture.assets.openedFiles;
                require(openedFiles > 0, "Initial installation did not read packaged assets");
                fixture.assets.unavailable = true;
                RuntimeAssets.install(fixture.context);
                require(fixture.assets.openedFiles == openedFiles, "Unchanged installation recopied assets");
                require(read(fixture.installed.resolve(GAME)).equals("old game"), "Initial game payload changed");
                require(read(fixture.installed.resolve(PYTHON)).equals("old python"), "Initial Python payload changed");
                fixture.checkSave();
            }
            private static void legacyMarker(Fixture fixture) throws IOException {
                fixture.updatePayload();
                write(fixture.installed.resolve(GAME), "old game");
                write(fixture.installed.resolve(PYTHON), "old python");
                write(fixture.installed.resolve("runtime/obsolete.txt"), "obsolete game");
                write(fixture.installed.resolve("python/lib/python3.14/obsolete.py"), "obsolete python");
                write(fixture.installed.resolve(MARKER), "1");
                RuntimeAssets.install(fixture.context);
                fixture.checkUpdatedPayload();
                require(!read(fixture.installed.resolve(MARKER)).equals("1"), "Legacy marker was retained");
            }
            private static void failedUpdateRetry(Fixture fixture) throws IOException {
                RuntimeAssets.install(fixture.context);
                String oldMarker = read(fixture.installed.resolve(MARKER));
                fixture.updatePayload();
                fixture.info.lastUpdateTime = 200;
                fixture.assets.failPath = PYTHON;
                boolean failed = false;
                try {
                    RuntimeAssets.install(fixture.context);
                } catch (IllegalStateException exception) {
                    require(exception.getCause() instanceof IOException, "Unexpected extraction failure");
                    failed = true;
                }
                require(failed, "Replacement installation ignored the updated payload");
                require(!Files.exists(fixture.installed.resolve("runtime")), "Partial game payload was retained");
                require(!Files.exists(fixture.installed.resolve("python")), "Partial Python payload was retained");
                require(read(fixture.installed.resolve(MARKER)).equals(oldMarker),
                        "Failed install committed its marker");
                fixture.checkSave();
                fixture.assets.failPath = null;
                RuntimeAssets.install(fixture.context);
                fixture.checkUpdatedPayload();
                require(!read(fixture.installed.resolve(MARKER)).equals(oldMarker),
                        "Retry did not commit update identity");
                fixture.assets.unavailable = true;
                RuntimeAssets.install(fixture.context);
            }
            public static void main(String[] arguments) throws IOException {
                Fixture fixture = new Fixture(Path.of(arguments[1]));
                switch (arguments[0]) {
                    case "same-version-update": sameVersionUpdate(fixture); break;
                    case "unchanged-install": unchangedInstall(fixture); break;
                    case "legacy-marker": legacyMarker(fixture); break;
                    case "failed-update-retry": failedUpdateRetry(fixture); break;
                    default: throw new AssertionError("Unknown scenario: " + arguments[0]);
                }
                System.out.println("Runtime assets regression passed: " + arguments[0]);
            }
        }
    """,
}


class AndroidRuntimeAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = shutil.which("java")
        if cls.java is None:
            raise unittest.SkipTest("Java is required for the Android runtime-assets regression")
        javac = shutil.which("javac")
        compiler = [javac] if javac else [cls.java, "-m", "jdk.compiler/com.sun.tools.javac.Main"]
        available = subprocess.run(compiler + ["-version"], capture_output=True, text=True, timeout=15)
        if available.returncode != 0:
            raise unittest.SkipTest("A Java compiler is required for the Android runtime-assets regression")
        temporary = tempfile.TemporaryDirectory(prefix="nouraajd-runtime-assets-")
        cls.addClassCleanup(temporary.cleanup)
        cls.project = Path(temporary.name)
        sources = []
        for name, source in JAVA_SOURCES.items():
            path = cls.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            sources.append(str(path))
        sources.append(str(RUNTIME_SOURCE))
        cls.classes = cls.project / "classes"
        cls.classes.mkdir()
        compiled = subprocess.run(
            compiler + ["-encoding", "UTF-8", "-d", str(cls.classes)] + sources,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compiled.returncode != 0:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def runScenario(self, scenario):
        completed = subprocess.run(
            [
                self.java,
                "-cp",
                str(self.classes),
                "com.lisu188.fallofnouraajd.RuntimeAssetsHarness",
                scenario,
                str(self.project / scenario),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("Runtime assets regression passed: " + scenario, completed.stdout)

    def testSameVersionReplacementRefreshesPayloadsAndPreservesSaves(self):
        self.runScenario("same-version-update")

    def testUnchangedInstallationSkipsAssetExtraction(self):
        self.runScenario("unchanged-install")

    def testLegacyVersionMarkerIsMigrated(self):
        self.runScenario("legacy-marker")

    def testFailedUpdateIsCleanedAndRetriedWithoutAnotherPackageChange(self):
        self.runScenario("failed-update-retry")


if __name__ == "__main__":
    unittest.main()
