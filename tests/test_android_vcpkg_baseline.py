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


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("bash"),
    "POSIX Git is required",
)
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
        self.git(
            "-C", str(self.source), "config", "user.email", "fixture@example.invalid"
        )
        versions = self.source / "versions"
        (versions / "f-").mkdir(parents=True)
        self.writeVersionDatabase("1")
        executable = self.source / "vcpkg"
        # This stop marker checks the real checkout before installation. It is
        # deliberately not a substitute for vcpkg resolution or Android builds.
        executable.write_text(
            "#!/bin/sh\nset -eu\n"
            'registry="$(dirname "$0")"\n'
            'test "$(git -C "$registry" rev-parse HEAD)" = "$GAME_TEST_EXPECTED_HEAD"\n'
            'cmp "$registry/versions/baseline.json" "$GAME_TEST_EXPECTED_BASELINE_FILE"\n'
            'cmp "$registry/versions/f-/fixture.json" "$GAME_TEST_EXPECTED_VERSION_FILE"\n'
            'printf "%s\\n" "$GAME_TEST_EXPECTED_HEAD" > "$GAME_TEST_INSTALL_LOG"\nexit 88\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)
        self.git("-C", str(self.source), "add", ".")
        self.git("-C", str(self.source), "commit", "-qm", "Fallback registry")
        self.fallback = self.git(
            "-C", str(self.source), "rev-parse", "HEAD"
        ).stdout.strip()
        self.tag = "2026.05.25"
        self.git(
            "-C", str(self.source), "tag", "-a", self.tag, "-m", "Fallback registry tag"
        )
        # Match the real failure: the manifest needs versions newer than the tag.
        self.writeVersionDatabase("2")
        self.git("-C", str(self.source), "commit", "-qam", "Manifest registry")
        self.baseline = self.git(
            "-C", str(self.source), "rev-parse", "HEAD"
        ).stdout.strip()
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
        (ndk / "source.properties").write_text(
            "Pkg.Revision = 29.0.14206865\n", encoding="utf-8"
        )
        self.log = self.root / "install.log"
        self.expectedBaselineFile = self.root / "expected-baseline.json"
        self.expectedVersionFile = self.root / "expected-fixture.json"
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
            "GAME_ANDROID_PYTHON_VERSION": "3.14.7",
            "GAME_ANDROID_PYTHON_SHA256": hashlib.sha256(archive).hexdigest(),
            "ANDROID_NDK_HOME": str(ndk),
            "GAME_TEST_INSTALL_LOG": str(self.log),
            "GAME_TEST_EXPECTED_BASELINE_FILE": str(self.expectedBaselineFile),
            "GAME_TEST_EXPECTED_VERSION_FILE": str(self.expectedVersionFile),
        }
        self.env.pop("GAME_ANDROID_VCPKG_REF", None)
        self.expectRegistry(self.baseline)

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            env=self.gitEnv,
            check=True,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def writeVersionDatabase(self, version):
        versions = self.source / "versions"
        (versions / "baseline.json").write_text(
            json.dumps({"default": {"fixture": {"baseline": version}}}) + "\n",
            encoding="utf-8",
        )
        (versions / "f-/fixture.json").write_text(
            json.dumps({"versions": [{"version": version, "git-tree": "a" * 40}]})
            + "\n",
            encoding="utf-8",
        )

    def writeManifest(self, baseline):
        manifest = {"builtin-baseline": baseline} if baseline is not None else {}
        self.manifest.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    def expectRegistry(self, commit):
        self.env["GAME_TEST_EXPECTED_HEAD"] = commit
        for path, destination in (
            ("versions/baseline.json", self.expectedBaselineFile),
            ("versions/f-/fixture.json", self.expectedVersionFile),
        ):
            destination.write_text(
                self.git("-C", str(self.source), "show", f"{commit}:{path}").stdout,
                encoding="utf-8",
            )

    def cachedCheckout(self, ref, shallow=True):
        self.git("init", "-q", str(self.checkout))
        self.git(
            "-C", str(self.checkout), "remote", "add", "origin", self.remote.as_uri()
        )
        depth = ["--depth", "1"] if shallow else []
        self.git("-C", str(self.checkout), "fetch", "-q", *depth, "origin", ref)
        self.git("-C", str(self.checkout), "checkout", "-q", "--detach", "FETCH_HEAD")

    def runBootstrap(self):
        before = self.manifest.read_bytes()
        result = subprocess.run(
            ["bash", str(self.project / "android/bootstrap-deps.sh")],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(
            before, self.manifest.read_bytes(), "Bootstrap changed the dependency pin"
        )
        return result

    def assertInstallReached(self, result):
        self.assertEqual(88, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            self.env["GAME_TEST_EXPECTED_HEAD"] + "\n",
            self.log.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            self.env["GAME_TEST_EXPECTED_HEAD"],
            self.git("-C", str(self.checkout), "rev-parse", "HEAD").stdout.strip(),
        )

    def test_cold_clone_checks_out_manifest_baseline_and_version_database(self):
        self.assertInstallReached(self.runBootstrap())
        self.assertEqual(
            "true",
            self.git(
                "-C", str(self.checkout), "rev-parse", "--is-shallow-repository"
            ).stdout.strip(),
        )

    def test_shallow_baseline_cache_needs_no_remote_fetch(self):
        self.cachedCheckout(self.baseline)
        self.git(
            "-C",
            str(self.checkout),
            "remote",
            "set-url",
            "origin",
            str(self.root / "unavailable.git"),
        )
        self.assertInstallReached(self.runBootstrap())

    def test_complete_baseline_cache_needs_no_remote_fetch(self):
        self.cachedCheckout(self.baseline, shallow=False)
        self.git(
            "-C",
            str(self.checkout),
            "remote",
            "set-url",
            "origin",
            str(self.root / "unavailable.git"),
        )
        self.assertInstallReached(self.runBootstrap())

    def test_stale_shallow_cache_is_rejected_without_changing_checkout(self):
        self.cachedCheckout(self.tag)
        result = self.runBootstrap()
        self.assertEqual(7, result.returncode, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(
            self.fallback,
            self.git("-C", str(self.checkout), "rev-parse", "HEAD").stdout.strip(),
        )

    def test_complete_cache_with_baseline_object_but_old_version_database_is_rejected(
        self,
    ):
        self.cachedCheckout(self.tag, shallow=False)
        self.git("-C", str(self.checkout), "fetch", "-q", "origin", self.baseline)
        result = self.runBootstrap()
        self.assertEqual(7, result.returncode, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(
            self.fallback,
            self.git("-C", str(self.checkout), "rev-parse", "HEAD").stdout.strip(),
        )

    def test_explicit_ref_override_retains_annotated_tag_selection(self):
        self.env["GAME_ANDROID_VCPKG_REF"] = self.tag
        self.expectRegistry(self.fallback)
        self.assertInstallReached(self.runBootstrap())
        self.assertInstallReached(self.runBootstrap())

    def test_manifest_without_baseline_retains_tag_fallback(self):
        self.writeManifest(None)
        self.expectRegistry(self.fallback)
        self.assertInstallReached(self.runBootstrap())
        self.assertInstallReached(self.runBootstrap())

    def test_unavailable_baseline_stops_before_install(self):
        self.writeManifest("f" * 40)
        result = self.runBootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())

    def test_invalid_baseline_stops_before_install(self):
        self.writeManifest("not-a-valid-registry-ref")
        result = self.runBootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
