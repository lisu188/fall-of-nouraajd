QMAKE_CXXFLAGS += -std=c++11 "-include cmath" -Wno-unused-local-typedefs -Wno-missing-field-initializers
QMAKE_CXXFLAGS_RELEASE -= -Os
QMAKE_CXXFLAGS_RELEASE -= -O
QMAKE_CXXFLAGS_RELEASE -= -O1
QMAKE_CXXFLAGS_RELEASE -= -O2
QMAKE_CXXFLAGS_RELEASE *= -O3
QMAKE_CXXFLAGS_RELEASE += -flto -march=native
QMAKE_LFLAGS_RELEASE -= -Os
QMAKE_LFLAGS_RELEASE -= -O
QMAKE_LFLAGS_RELEASE -= -O1
QMAKE_LFLAGS_RELEASE -= -O2
QMAKE_LFLAGS_RELEASE *= -O3
QMAKE_LFLAGS_RELEASE += -flto -march=native
QMAKE_CXXFLAGS_DEBUG -= -g
QMAKE_CXXFLAGS_DEBUG -= -g0
QMAKE_CXXFLAGS_DEBUG -= -g1
QMAKE_CXXFLAGS_DEBUG -= -g2
QMAKE_CXXFLAGS_DEBUG *= -g3

DEFINES += "QT_NO_KEYWORDS"

win32{
    INCLUDEPATH += C:\boost-include
    DEPENDPATH += C:\boost-include
    INCLUDEPATH += C:\Python34\include
    DEPENDPATH += C:\Python34\include
}

unix{
    INCLUDEPATH += /usr/local/include/python3.4m
    DEPENDPATH += /usr/local/include/python3.4m
    INCLUDEPATH += /usr/include
    DEPENDPATH += /usr/include
}
