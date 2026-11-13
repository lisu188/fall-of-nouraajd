import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "android/bootstrap-deps.sh").read_text(encoding="utf-8")


@unittest.skipUnless(os.name == "posix" and shutil.which("git") and shutil.which("bash"), "POSIX Git is required")
class AndroidVcpkgBaselineTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="android-vcpkg-baseline-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.gitEnv = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "0",
        }
        self.source = self.root / "registry source"
        self.source.mkdir()
        self.git("init", "-q", str(self.source))
        self.git("-C", str(self.source), "config", "user.name", "Fixture")
        self.git("-C", str(self.source), "config", "user.email", "fixture@example.invalid")
        versions = self.source / "versions"
        versions.mkdir()
        (versions / "baseline.json").write_text('{"default": {}}\n', encoding="utf-8")
        executable = self.source / "vcpkg"
        executable.write_text(
            '#!/bin/sh\nset -eu\n'
            'git -C "$(dirname "$0")" cat-file -e "$GAME_TEST_BASELINE:versions/baseline.json"\n'
            'printf "%s\\n" "$GAME_TEST_BASELINE" > "$GAME_TEST_INSTALL_LOG"\nexit 88\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)
        self.git("-C", str(self.source), "add", ".")
        self.git("-C", str(self.source), "commit", "-qm", "Pinned engine")
        self.engine = self.git("-C", str(self.source), "rev-parse", "HEAD").stdout.strip()
        self.tag = "fixture-engine"
        self.git("-C", str(self.source), "tag", self.tag)
        # The real manifest baseline is newer than the pinned engine tag.
        (versions / "baseline.json").write_text('{"default": {"fixture": {"baseline": "1"}}}\n', encoding="utf-8")
        self.git("-C", str(self.source), "commit", "-qam", "Newer registry baseline")
        self.baseline = self.git("-C", str(self.source), "rev-parse", "HEAD").stdout.strip()
        self.remote = self.root / "registry.git"
        self.git("clone", "-q", "--bare", str(self.source), str(self.remote))
        self.project = self.root / "project"
        script = self.project / "android/bootstrap-deps.sh"
        script.parent.mkdir(parents=True)
        script.write_text(BOOTSTRAP, encoding="utf-8")
        self.manifest = self.project / "vcpkg.json"
        self.writeManifest(self.baseline)
        self.deps = self.root / "dependencies"
        self.deps.mkdir()
        self.checkout = self.deps / "vcpkg"
        archive = b"preverified Python fixture archive"
        (self.deps / "python-3.14.7-aarch64-linux-android.tar.gz").write_bytes(archive)
        python = self.deps / "python-3.14.7-aarch64-linux-android"
        (python / "lib/python3.14").mkdir(parents=True)
        (python / "lib/libpython3.14.so").touch()
        (python / "include/python3.14").mkdir(parents=True)
        (python / "include/python3.14/Python.h").touch()
        ndk = self.root / "ndk"
        ndk.mkdir()
        (ndk / "source.properties").write_text("Pkg.Revision = 29.0.14206865\n", encoding="utf-8")
        self.log = self.root / "install.log"
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": f"url.{self.remote.as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/microsoft/vcpkg.git",
            "GIT_CONFIG_KEY_1": "protocol.file.allow",
            "GIT_CONFIG_VALUE_1": "always",
            "GAME_ANDROID_DEPS_DIR": str(self.deps),
            "GAME_ANDROID_VCPKG_REF": self.tag,
            "GAME_ANDROID_PYTHON_VERSION": "3.14.7",
            "GAME_ANDROID_PYTHON_SHA256": hashlib.sha256(archive).hexdigest(),
            "ANDROID_NDK_HOME": str(ndk),
            "GAME_TEST_BASELINE": self.baseline,
            "GAME_TEST_INSTALL_LOG": str(self.log),
        }

    def git(self, *args):
        return subprocess.run(["git", *args], env=self.gitEnv, check=True, text=True, capture_output=True, timeout=20)

    def writeManifest(self, baseline):
        self.manifest.write_text(json.dumps({"builtin-baseline": baseline}) + "\n", encoding="utf-8")

    def cachedCheckout(self, shallow):
        args = ["clone", "-q", "--branch", self.tag]
        if shallow:
            args += ["--depth", "1"]
        self.git(*args, self.remote.as_uri(), str(self.checkout))

    def runBootstrap(self):
        before = self.manifest.read_bytes()
        result = subprocess.run(
            ["bash", str(self.project / "android/bootstrap-deps.sh")],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(before, self.manifest.read_bytes(), "Bootstrap changed the dependency pin")
        if self.checkout.exists():
            self.assertEqual(self.engine, self.git("-C", str(self.checkout), "rev-parse", "HEAD").stdout.strip())
        return result

    def assertInstallReached(self, result):
        self.assertEqual(88, result.returncode, result.stdout + result.stderr)
        self.assertEqual(self.baseline + "\n", self.log.read_text(encoding="utf-8"))
        self.assertEqual(
            "false", self.git("-C", str(self.checkout), "rev-parse", "--is-shallow-repository").stdout.strip()
        )

    def test_cold_clone_fetches_newer_baseline_without_changing_engine(self):
        self.assertInstallReached(self.runBootstrap())

    def test_shallow_cache_fetches_newer_baseline_without_changing_engine(self):
        self.cachedCheckout(shallow=True)
        self.assertInstallReached(self.runBootstrap())

    def test_complete_cache_needs_no_remote_fetch(self):
        self.cachedCheckout(shallow=False)
        self.git("-C", str(self.checkout), "remote", "set-url", "origin", str(self.root / "unavailable.git"))
        self.assertInstallReached(self.runBootstrap())

    def test_complete_cache_fetches_missing_newer_baseline(self):
        self.cachedCheckout(shallow=True)
        self.git("-C", str(self.checkout), "fetch", "--unshallow", "origin", self.tag)
        self.assertInstallReached(self.runBootstrap())

    def test_unavailable_baseline_stops_before_install(self):
        self.cachedCheckout(shallow=True)
        self.writeManifest("f" * 40)
        result = self.runBootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())

    def test_invalid_baseline_stops_before_install(self):
        self.cachedCheckout(shallow=False)
        self.writeManifest("main")
        result = self.runBootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())
        self.assertIn("40-character builtin-baseline", result.stderr)


if __name__ == "__main__":
    unittest.main()
