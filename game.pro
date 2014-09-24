TEMPLATE = subdirs
TARGET = all
SUBDIRS = \
        python \
        game \
    resources

game.depends = python
game.depends = resources

OTHER_FILES += \
    format.py
    game.pri
