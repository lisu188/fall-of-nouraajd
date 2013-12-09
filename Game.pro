QT += core gui widgets

TARGET = LegacyGame2013
TEMPLATE = app
CONFIG += c++11

INCLUDEPATH += $$PWD
DEPENDPATH += $$PWD

SOURCES += $$files($$PWD/*.cpp, true)
SOURCES -= $$files($$PWD/moc_*.cpp, true)
HEADERS += $$files($$PWD/*.h, true)
