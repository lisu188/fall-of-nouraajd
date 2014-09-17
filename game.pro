TEMPLATE = subdirs
SUBDIRS = \
        python \
        core

core.depends = python
