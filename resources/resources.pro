TARGET = resources
TEMPLATE = lib
CONFIG+= staticlib

include(../game.pri)

SOURCES += CResourcesHandler.cpp

HEADERS += CResourcesHandler.h

RESOURCES += \
    config.qrc \
    scripts.qrc \
    maps.qrc \
    images.qrc

OTHER_FILES +=
