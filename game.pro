TEMPLATE = subdirs
TARGET = all
SUBDIRS = \
        python \
        game


game.depends = python

OTHER_FILES += \
    format.py
    game.pri
