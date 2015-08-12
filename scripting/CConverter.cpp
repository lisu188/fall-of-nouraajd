#include "CConverter.h"
#include "CGlobal.h"
#include "object/CObject.h"

using namespace boost::python;

struct QString_to_python_str {
    static PyObject* convert ( QString const& s ) {
        return incref ( object ( s.toUtf8().constData() ).ptr() );
    }
};

struct QString_from_python_str {
    QString_from_python_str() {
        converter::registry::push_back (
        [] ( PyObject* obj_ptr ) ->void* {
            if ( !    PyUnicode_Check ( obj_ptr ) ) { return nullptr; }
            return obj_ptr;
        },
        [] (
            PyObject* obj_ptr,
            converter::rvalue_from_python_stage1_data* data ) {
            const char* value = _PyUnicode_AsString ( obj_ptr );
            void* storage = ( ( converter::rvalue_from_python_storage<QString>* ) data )->storage.bytes;
            new ( storage ) QString ( value );
            data->convertible = storage;
        },
        boost::python::type_id<QString>() );
    }
};

template <typename Return,typename... Args>
struct builder {
    static void build ( PyObject* obj_ptr,converter::rvalue_from_python_stage1_data* data ) {
        help ( obj_ptr,data );
    }
    template<typename R=Return>
    static void help ( PyObject* obj_ptr,converter::rvalue_from_python_stage1_data* data,
                       typename vstd::disable_if<vstd::is_shared_ptr<R>::value>::type* =0 ) {
        void* storage = ( ( converter::rvalue_from_python_storage
                            <std::function<R ( Args... ) >>* ) data )->storage.bytes;
        object func=object ( handle<> ( borrowed ( incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<R ( Args... ) > ( [func] ( Args... args ) {
            return extract<R> ( incref ( func ( args... ).ptr() ) );
        } );
        data->convertible = storage;
    }
    template<typename R=Return>
    static void help ( PyObject* obj_ptr,converter::rvalue_from_python_stage1_data* data,
                       typename vstd::enable_if<vstd::is_shared_ptr<R>::value>::type* =0 ) {
        typedef typename R::element_type* ptr_type;
        void* storage = ( ( converter::rvalue_from_python_storage
                            <std::function<R ( Args... ) >>* ) data )->storage.bytes;
        object func=object ( handle<> ( borrowed ( incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<R ( Args... ) > ( [func] ( Args... args ) {
            return R ( vstd::call<ptr_type> ( extract<ptr_type> ( incref ( func ( args... ).ptr() ) ) )  );
        } );
        data->convertible = storage;
    }
};

template <typename... Args>
struct builder<void,Args...> {
    static void build ( PyObject* obj_ptr,converter::rvalue_from_python_stage1_data* data ) {
        void* storage = ( ( converter::rvalue_from_python_storage
                            <std::function<void ( Args... ) >>* ) data )->storage.bytes;
        object func=object ( handle<> ( borrowed ( incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<void ( Args... ) > ( [func] ( Args... args ) {
            func ( args... );
        } );
        data->convertible = storage;
    }
};

template <typename... Args>
struct builder<bool,Args...> {
    static void build ( PyObject* obj_ptr,converter::rvalue_from_python_stage1_data* data ) {
        void* storage = ( ( converter::rvalue_from_python_storage
                            <std::function<bool ( Args... ) >>* ) data )->storage.bytes;
        object func=object ( handle<> ( borrowed ( incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<bool ( Args... ) > ( [func] ( Args... args ) {
            return func ( args... ).ptr() == Py_True;
        } );
        data->convertible = storage;
    }
};

template<typename Return,typename... Args>
struct function_converter {
    function_converter() {
        converter::registry::push_back (
        [] ( PyObject* obj_ptr ) ->void* {
            if ( PyCallable_Check ( obj_ptr ) ) { return obj_ptr; }
            return nullptr;
        },
        builder<Return,Args...>::build,
        boost::python::type_id<std::function<Return ( Args... ) >>() );
    }
};

void initialize_converters() {
    to_python_converter<QString,QString_to_python_str>();

    QString_from_python_str();

    function_converter<std::shared_ptr<CGameObject>>();

    function_converter<void,std::shared_ptr<CMapObject>>();
    function_converter<bool,std::shared_ptr<CMapObject>>();

    implicitly_convertible<std::shared_ptr<CTrigger>,std::shared_ptr<CGameObject>>();
}
