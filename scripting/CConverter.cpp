#include "CConverter.h"
#include "core/CGlobal.h"
#include "object/CObject.h"

struct QString_to_python_str {
    static PyObject *convert(QString const &s) {
        return boost::python::incref(boost::python::object(s.toUtf8().constData()).ptr());
    }
};

struct QString_from_python_str {
    QString_from_python_str() {
        boost::python::converter::registry::push_back(
                [](PyObject *obj_ptr) -> void * {
                    if (!PyUnicode_Check (obj_ptr)) { return nullptr; }
                    return obj_ptr;
                },
                [](
                        PyObject *obj_ptr,
                        boost::python::converter::rvalue_from_python_stage1_data *data) {
                    const char *value = _PyUnicode_AsString(obj_ptr);
                    void *storage = ((boost::python::converter::rvalue_from_python_storage<QString> *) data)->storage.bytes;
                    new(storage) QString(value);
                    data->convertible = storage;
                },
                boost::python::type_id<QString>());
    }
};

void initialize_converters() {
    boost::python::to_python_converter<QString, QString_to_python_str>();
    QString_from_python_str();
}
