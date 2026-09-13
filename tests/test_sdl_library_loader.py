import ctypes
import ctypes.util
import unittest
from pathlib import Path
from unittest.mock import patch

import test as game_tests


class SdlLibraryLoaderTest(unittest.TestCase):
    def setUp(self):
        resolver = getattr(game_tests, "resolveSdlLibraryName", None)
        if resolver is not None:
            resolver.cache_clear()
            self.addCleanup(resolver.cache_clear)

    def test_repeated_loads_resolve_once_and_return_fresh_wrappers(self):
        def loadLibrary(name):
            if name == "discovered-sdl":
                return object()
            raise OSError(name)

        with patch.object(ctypes, "CDLL", side_effect=loadLibrary), patch.object(
            ctypes.util, "find_library", return_value="discovered-sdl"
        ) as discover:
            libraries = [game_tests.load_sdl_library() for _ in range(40)]
        self.assertEqual(1, discover.call_count)
        self.assertEqual(40, len({id(library) for library in libraries}))

    def test_active_build_config_precedes_system_library_and_invalidates_resolution(self):
        build_path = Path("active-build")
        release = str(build_path / "Release" / "SDL2.dll")
        debug = str(build_path / "Debug" / "SDL2.dll")

        def loadLibrary(name):
            if name in {release, debug, "system-sdl"}:
                return name
            raise OSError(name)

        with patch.object(game_tests, "build_dir", build_path), patch.object(
            ctypes, "CDLL", side_effect=loadLibrary
        ), patch.object(ctypes.util, "find_library", return_value="system-sdl") as discover:
            with patch.object(game_tests, "extension_dirs", [build_path / "Release"]):
                self.assertEqual(release, game_tests.load_sdl_library())
            with patch.object(game_tests, "extension_dirs", [build_path / "Debug"]):
                self.assertEqual(debug, game_tests.load_sdl_library())
        discover.assert_not_called()

    def test_known_linux_soname_avoids_compiler_based_discovery(self):
        def loadLibrary(name):
            if name == "libSDL2-2.0.so.0":
                return name
            raise OSError(name)

        with patch.object(ctypes, "CDLL", side_effect=loadLibrary), patch.object(
            ctypes.util, "find_library", return_value=None
        ) as discover:
            self.assertEqual("libSDL2-2.0.so.0", game_tests.load_sdl_library())
        discover.assert_not_called()

    def test_failed_resolution_can_be_retried(self):
        with patch.object(ctypes, "CDLL", side_effect=OSError), patch.object(
            ctypes.util, "find_library", return_value=None
        ):
            with self.assertRaisesRegex(AssertionError, "Could not load SDL2"):
                game_tests.load_sdl_library()
        with patch.object(ctypes, "CDLL", return_value="available"):
            self.assertEqual("available", game_tests.load_sdl_library())


if __name__ == "__main__":
    unittest.main()
