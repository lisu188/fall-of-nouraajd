# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original qmake pin and compiler-selection regressions for static LTO archives."""

from pathlib import Path
import tempfile
import unittest

from scripts import history_static_lto as static_lto

FIXTURES = [
    {
        "contents": {
            "python/python.pro": " # ------------------------------------------------ -\n #\n # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43\n #\n # ------------------------------------------------ -\n\nTARGET = python\nTEMPLATE = lib\nCONFIG+= staticlib\n\ninclude(../game.pri)\n\nSOURCES += \\\n    dict.cpp \\\n    errors.cpp \\\n    exec.cpp \\\n    import.cpp \\\n    list.cpp \\\n    long.cpp \\\n    module.cpp \\\n    numeric.cpp \\\n    object_operators.cpp \\\n    object_protocol.cpp \\\n    slice.cpp \\\n    str.cpp \\\n    tuple.cpp \\\n    wrapper.cpp \\\n    object/class.cpp \\\n    object/enum.cpp \\\n    object/function.cpp \\\n    object/function_doc_signature.cpp \\\n    object/inheritance.cpp \\\n    object/iterator.cpp \\\n    object/life_support.cpp \\\n    object/pickle_support.cpp \\\n    object/stl_iterator.cpp \\\n    converter/arg_to_python_base.cpp \\\n    converter/builtin_converters.cpp \\\n    converter/from_python.cpp \\\n    converter/registry.cpp \\\n    converter/type_id.cpp\n\n\nLIBS += -L/lib64/ -lpython3.3m\n\n\n",
            "game.pri": 'QMAKE_CXXFLAGS += -std=c++11\nQMAKE_CXXFLAGS_RELEASE -= -Os\nQMAKE_CXXFLAGS_RELEASE -= -O\nQMAKE_CXXFLAGS_RELEASE -= -O1\nQMAKE_CXXFLAGS_RELEASE -= -O2\nQMAKE_CXXFLAGS_RELEASE *= -O3\nQMAKE_CXXFLAGS_RELEASE += -flto -march=native\nQMAKE_LFLAGS_RELEASE -= -Os\nQMAKE_LFLAGS_RELEASE -= -O\nQMAKE_LFLAGS_RELEASE -= -O1\nQMAKE_LFLAGS_RELEASE -= -O2\nQMAKE_LFLAGS_RELEASE *= -O3\nQMAKE_LFLAGS_RELEASE += -flto -march=native\nQMAKE_CXXFLAGS_DEBUG -= -g\nQMAKE_CXXFLAGS_DEBUG -= -g0\nQMAKE_CXXFLAGS_DEBUG -= -g1\nQMAKE_CXXFLAGS_DEBUG -= -g2\nQMAKE_CXXFLAGS_DEBUG *= -g3\n\nINCLUDEPATH += /usr/include/python3.3m\nDEPENDPATH += /usr/include/python3.3m\n\nINCLUDEPATH += /usr/include\nDEPENDPATH += /usr/include\n\nDEFINES += "QT_NO_KEYWORDS"\n',
        },
        "indices": [269],
    },
    {
        "contents": {
            "python/python.pro": " # ------------------------------------------------ -\n #\n # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43\n #\n # ------------------------------------------------ -\n\nTARGET = python\nTEMPLATE = lib\nCONFIG+= staticlib\n\ninclude(../game.pri)\n\nSOURCES += \\\n    dict.cpp \\\n    errors.cpp \\\n    exec.cpp \\\n    import.cpp \\\n    list.cpp \\\n    long.cpp \\\n    module.cpp \\\n    numeric.cpp \\\n    object_operators.cpp \\\n    object_protocol.cpp \\\n    slice.cpp \\\n    str.cpp \\\n    tuple.cpp \\\n    wrapper.cpp \\\n    object/class.cpp \\\n    object/enum.cpp \\\n    object/function.cpp \\\n    object/function_doc_signature.cpp \\\n    object/inheritance.cpp \\\n    object/iterator.cpp \\\n    object/life_support.cpp \\\n    object/pickle_support.cpp \\\n    object/stl_iterator.cpp \\\n    converter/arg_to_python_base.cpp \\\n    converter/builtin_converters.cpp \\\n    converter/from_python.cpp \\\n    converter/registry.cpp \\\n    converter/type_id.cpp\n\n\nunix:LIBS += -L/lib64/ -lpython3.3m\n\nwin32:LIBS += -LC:\\Python34\\libs -lpython34\n\n\n\n",
            "game.pri": 'QMAKE_CXXFLAGS += -std=c++11 "-include cmath"\nQMAKE_CXXFLAGS_RELEASE -= -Os\nQMAKE_CXXFLAGS_RELEASE -= -O\nQMAKE_CXXFLAGS_RELEASE -= -O1\nQMAKE_CXXFLAGS_RELEASE -= -O2\nQMAKE_CXXFLAGS_RELEASE *= -O3\nQMAKE_CXXFLAGS_RELEASE += -flto -march=native\nQMAKE_LFLAGS_RELEASE -= -Os\nQMAKE_LFLAGS_RELEASE -= -O\nQMAKE_LFLAGS_RELEASE -= -O1\nQMAKE_LFLAGS_RELEASE -= -O2\nQMAKE_LFLAGS_RELEASE *= -O3\nQMAKE_LFLAGS_RELEASE += -flto -march=native\nQMAKE_CXXFLAGS_DEBUG -= -g\nQMAKE_CXXFLAGS_DEBUG -= -g0\nQMAKE_CXXFLAGS_DEBUG -= -g1\nQMAKE_CXXFLAGS_DEBUG -= -g2\nQMAKE_CXXFLAGS_DEBUG *= -g3\n\nDEFINES += "QT_NO_KEYWORDS"\n\nwin32:INCLUDEPATH += C:\\boost-include\nwin32:DEPENDPATH += C:\\boost-include\n\nwin32:INCLUDEPATH += C:\\Python34\\include\nwin32:DEPENDPATH += C:\\Python34\\include\n',
        },
        "indices": [270, 271],
    },
    {
        "contents": {
            "python/python.pro": " # ------------------------------------------------ -\n #\n # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43\n #\n # ------------------------------------------------ -\n\nTARGET = python\nTEMPLATE = lib\nCONFIG+= staticlib\n\ninclude(../game.pri)\n\nSOURCES += \\\n    dict.cpp \\\n    errors.cpp \\\n    exec.cpp \\\n    import.cpp \\\n    list.cpp \\\n    long.cpp \\\n    module.cpp \\\n    numeric.cpp \\\n    object_operators.cpp \\\n    object_protocol.cpp \\\n    slice.cpp \\\n    str.cpp \\\n    tuple.cpp \\\n    wrapper.cpp \\\n    object/class.cpp \\\n    object/enum.cpp \\\n    object/function.cpp \\\n    object/function_doc_signature.cpp \\\n    object/inheritance.cpp \\\n    object/iterator.cpp \\\n    object/life_support.cpp \\\n    object/pickle_support.cpp \\\n    object/stl_iterator.cpp \\\n    converter/arg_to_python_base.cpp \\\n    converter/builtin_converters.cpp \\\n    converter/from_python.cpp \\\n    converter/registry.cpp \\\n    converter/type_id.cpp\n\n\nunix:LIBS += -L/lib64/ -lpython3.3m\n\nwin32:LIBS += -LC:\\Python34\\libs -lpython34\n\n\n\n",
            "game.pri": 'QMAKE_CXXFLAGS += -std=c++11 "-include cmath"\nQMAKE_CXXFLAGS_RELEASE -= -Os\nQMAKE_CXXFLAGS_RELEASE -= -O\nQMAKE_CXXFLAGS_RELEASE -= -O1\nQMAKE_CXXFLAGS_RELEASE -= -O2\nQMAKE_CXXFLAGS_RELEASE *= -O3\nQMAKE_CXXFLAGS_RELEASE += -flto -march=native\nQMAKE_LFLAGS_RELEASE -= -Os\nQMAKE_LFLAGS_RELEASE -= -O\nQMAKE_LFLAGS_RELEASE -= -O1\nQMAKE_LFLAGS_RELEASE -= -O2\nQMAKE_LFLAGS_RELEASE *= -O3\nQMAKE_LFLAGS_RELEASE += -flto -march=native\nQMAKE_CXXFLAGS_DEBUG -= -g\nQMAKE_CXXFLAGS_DEBUG -= -g0\nQMAKE_CXXFLAGS_DEBUG -= -g1\nQMAKE_CXXFLAGS_DEBUG -= -g2\nQMAKE_CXXFLAGS_DEBUG *= -g3\n\nDEFINES += "QT_NO_KEYWORDS"\n\nwin32{\nINCLUDEPATH += C:\\boost-include\nDEPENDPATH += C:\\boost-include\nINCLUDEPATH += C:\\Python34\\include\nDEPENDPATH += C:\\Python34\\include\n}\n\nunix{\n    INCLUDEPATH += /usr/include/python3.3m\n    DEPENDPATH += /usr/include/python3.3m\n}\n',
        },
        "indices": [272, 273, 274],
    },
    {
        "contents": {
            "python/python.pro": "TARGET = python\nTEMPLATE = lib\nCONFIG+= staticlib\n\ninclude(../game.pri)\n\nSOURCES += \\\n    dict.cpp \\\n    errors.cpp \\\n    exec.cpp \\\n    import.cpp \\\n    list.cpp \\\n    long.cpp \\\n    module.cpp \\\n    numeric.cpp \\\n    object_operators.cpp \\\n    object_protocol.cpp \\\n    slice.cpp \\\n    str.cpp \\\n    tuple.cpp \\\n    wrapper.cpp \\\n    object/class.cpp \\\n    object/enum.cpp \\\n    object/function.cpp \\\n    object/function_doc_signature.cpp \\\n    object/inheritance.cpp \\\n    object/iterator.cpp \\\n    object/life_support.cpp \\\n    object/pickle_support.cpp \\\n    object/stl_iterator.cpp \\\n    converter/arg_to_python_base.cpp \\\n    converter/builtin_converters.cpp \\\n    converter/from_python.cpp \\\n    converter/registry.cpp \\\n    converter/type_id.cpp\n\n\nunix:LIBS += -L/lib64/ -lpython3.3m\n\nwin32:LIBS += -LC:\\Python34\\libs -lpython34\n\n\n\n",
            "game.pri": 'QMAKE_CXXFLAGS += -std=c++11 "-include cmath"\nQMAKE_CXXFLAGS_RELEASE -= -Os\nQMAKE_CXXFLAGS_RELEASE -= -O\nQMAKE_CXXFLAGS_RELEASE -= -O1\nQMAKE_CXXFLAGS_RELEASE -= -O2\nQMAKE_CXXFLAGS_RELEASE *= -O3\nQMAKE_CXXFLAGS_RELEASE += -flto -march=native\nQMAKE_LFLAGS_RELEASE -= -Os\nQMAKE_LFLAGS_RELEASE -= -O\nQMAKE_LFLAGS_RELEASE -= -O1\nQMAKE_LFLAGS_RELEASE -= -O2\nQMAKE_LFLAGS_RELEASE *= -O3\nQMAKE_LFLAGS_RELEASE += -flto -march=native\nQMAKE_CXXFLAGS_DEBUG -= -g\nQMAKE_CXXFLAGS_DEBUG -= -g0\nQMAKE_CXXFLAGS_DEBUG -= -g1\nQMAKE_CXXFLAGS_DEBUG -= -g2\nQMAKE_CXXFLAGS_DEBUG *= -g3\n\nDEFINES += "QT_NO_KEYWORDS"\n\nwin32{\nINCLUDEPATH += C:\\boost-include\nDEPENDPATH += C:\\boost-include\nINCLUDEPATH += C:\\Python34\\include\nDEPENDPATH += C:\\Python34\\include\n}\n\nunix{\n    INCLUDEPATH += /usr/include/python3.3m\n    DEPENDPATH += /usr/include/python3.3m\n}\n',
        },
        "indices": [275, 276, 277, 278, 279, 280],
    },
]


class StaticLtoRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.recipe = {"compilerCommand": "g++-5", "qmakeArguments": ["QMAKE_CXX=g++-5"]}
        self.writeFixture(FIXTURES[0])

    def tearDown(self):
        self.temporary.cleanup()

    def writeFixture(self, fixture):
        for name, text in fixture["contents"].items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def testOriginalStaticLtoInputsSelectMatchingGccPlugin(self):
        for fixture in FIXTURES:
            with self.subTest(indices=fixture["indices"]):
                self.writeFixture(fixture)
                actual = static_lto.recipeForSource(self.recipe, self.root)
                self.assertEqual(actual["qmakeArguments"], ["QMAKE_CXX=g++-5", static_lto.ARGUMENT])
                self.assertEqual(self.recipe["qmakeArguments"], ["QMAKE_CXX=g++-5"])

    def testChangedOriginalInputDoesNotSelect(self):
        path = self.root / "game.pri"
        path.write_text(path.read_text() + "# unreviewed change\n")
        self.assertIs(static_lto.recipeForSource(self.recipe, self.root), self.recipe)

    def testMissingInputDoesNotSelect(self):
        (self.root / "game.pri").unlink()
        self.assertIs(static_lto.recipeForSource(self.recipe, self.root), self.recipe)

    def testMixedUnreviewedPinsDoNotSelect(self):
        (self.root / "python/python.pro").write_text(FIXTURES[1]["contents"]["python/python.pro"])
        self.assertIs(static_lto.recipeForSource(self.recipe, self.root), self.recipe)

    def testInputSymlinkDoesNotSelect(self):
        target = self.root / "common.pri"
        (self.root / "game.pri").rename(target)
        (self.root / "game.pri").symlink_to(target)
        self.assertIs(static_lto.recipeForSource(self.recipe, self.root), self.recipe)

    def testDependencyDirectorySymlinkDoesNotSelect(self):
        (self.root / "python").rename(self.root / "dependency")
        (self.root / "python").symlink_to(self.root / "dependency", target_is_directory=True)
        self.assertIs(static_lto.recipeForSource(self.recipe, self.root), self.recipe)

    def testAnotherCompilerDoesNotSelectGcc5(self):
        recipe = {"compilerCommand": "clang++", "qmakeArguments": ["QMAKE_CXX=clang++"]}
        self.assertIs(static_lto.recipeForSource(recipe, self.root), recipe)

    def testActualQmakeCompilerTakesPrecedence(self):
        recipe = {"compilerCommand": "g++-5", "qmakeArguments": ["QMAKE_CXX=clang++"]}
        self.assertIs(static_lto.recipeForSource(recipe, self.root), recipe)

    def testAbsoluteConfiguredGcc5UsesMatchingPlugin(self):
        recipe = {"compilerCommand": "/usr/bin/g++-5", "qmakeArguments": []}
        self.assertEqual(static_lto.recipeForSource(recipe, self.root)["qmakeArguments"], [static_lto.ARGUMENT])

    def testAlreadySelectedArchiverIsNotDuplicated(self):
        selected = static_lto.recipeForSource(self.recipe, self.root)
        self.assertIs(static_lto.recipeForSource(selected, self.root), selected)

    def testExplicitDifferentArchiverIsNotSilentlyOverridden(self):
        recipe = {**self.recipe, "qmakeArguments": ["QMAKE_CXX=g++-5", "QMAKE_AR=ar cqs"]}
        self.assertIs(static_lto.recipeForSource(recipe, self.root), recipe)


if __name__ == "__main__":
    unittest.main()
