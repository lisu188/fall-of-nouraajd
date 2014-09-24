TARGET = python
TEMPLATE = lib
CONFIG+= staticlib

include(../game.pri)

SOURCES += \
    dict.cpp \
    errors.cpp \
    exec.cpp \
    import.cpp \
    list.cpp \
    long.cpp \
    module.cpp \
    numeric.cpp \
    object_operators.cpp \
    object_protocol.cpp \
    slice.cpp \
    str.cpp \
    tuple.cpp \
    wrapper.cpp \
    object/class.cpp \
    object/enum.cpp \
    object/function.cpp \
    object/function_doc_signature.cpp \
    object/inheritance.cpp \
    object/iterator.cpp \
    object/life_support.cpp \
    object/pickle_support.cpp \
    object/stl_iterator.cpp \
    converter/arg_to_python_base.cpp \
    converter/builtin_converters.cpp \
    converter/from_python.cpp \
    converter/registry.cpp \
    converter/type_id.cpp


unix:LIBS += -L/usr/local/lib -lpython3.4m -ldl -fPIC -lutil

win32:LIBS += -LC:\Python34\libs -lpython34

HEADERS +=



