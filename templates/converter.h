#pragma once
#include "CGlobal.h"
#include "templates/cast.h"

template <typename Return,typename... Args>
struct builder {
    static void build ( PyObject* obj_ptr,boost::python::converter::rvalue_from_python_stage1_data* data ) {
        help ( obj_ptr,data );
    }
    template<typename R=Return>
    static void help ( PyObject* obj_ptr,
                       boost::python::converter::rvalue_from_python_stage1_data* data,
                       typename vstd::disable_if<vstd::is_shared_ptr<R>::value>::type* =0 ) {
        void* storage = ( ( boost::python::converter::rvalue_from_python_storage
                            <std::function<R ( Args... ) >>* ) data )->storage.bytes;
        boost::python::object func=
            boost::python::object ( boost::python::handle<> (
                                        boost::python::borrowed (
                                            boost::python::incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<R ( Args... ) > ( [func] ( Args... args ) {
            return boost::python::extract<R> (
                       boost::python::incref ( func ( args... ).ptr() ) );
        } );
        data->convertible = storage;
    }
    template<typename R=Return>
    static void help ( PyObject* obj_ptr,
                       boost::python::converter::rvalue_from_python_stage1_data* data,
                       typename vstd::enable_if<vstd::is_shared_ptr<R>::value>::type* =0 ) {
        typedef typename R::element_type* ptr_type;
        void* storage = ( ( boost::python::converter::rvalue_from_python_storage
                            <std::function<R ( Args... ) >>* ) data )->storage.bytes;
        boost::python::object func=boost::python::object (
                                       boost::python::handle<> ( boost::python::borrowed (
                                               boost::python::incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<R ( Args... ) > ( [func] ( Args... args ) {
            return R ( vstd::call (
                           boost::python::extract<ptr_type> (
                               boost::python::incref ( func ( args... ).ptr() ) ) )  );
        } );
        data->convertible = storage;
    }
};

template <typename... Args>
struct builder<void,Args...> {
    static void build ( PyObject* obj_ptr,
                        boost::python::converter::rvalue_from_python_stage1_data* data ) {
        void* storage = ( ( boost::python::converter::rvalue_from_python_storage
                            <std::function<void ( Args... ) >>* ) data )->storage.bytes;
        boost::python::object func=boost::python::object (
                                       boost::python::handle<> (
                                           boost::python::borrowed (
                                               boost::python::incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<void ( Args... ) > ( [func] ( Args... args ) {
            func ( args... );
        } );
        data->convertible = storage;
    }
};

template <typename... Args>
struct builder<bool,Args...> {
    static void build ( PyObject* obj_ptr,
                        boost::python::converter::rvalue_from_python_stage1_data* data ) {
        void* storage = ( ( boost::python::converter::rvalue_from_python_storage
                            <std::function<bool ( Args... ) >>* ) data )->storage.bytes;
        boost::python::object func=boost::python::object (
                                       boost::python::handle<> (
                                           boost::python::borrowed (
                                               boost::python::incref ( obj_ptr ) ) ) );
        new ( storage ) std::function<bool ( Args... ) > ( [func] ( Args... args ) {
            return func ( args... ).ptr() == Py_True;
        } );
        data->convertible = storage;
    }
};

template<typename Return,typename... Args>
struct function_converter {
    function_converter() {
        boost::python::converter::registry::push_back (
        [] ( PyObject* obj_ptr ) ->void* {
            if ( PyCallable_Check ( obj_ptr ) ) { return obj_ptr; }
            return nullptr;
        },
        builder<Return,Args...>::build,
        boost::python::type_id<std::function<Return ( Args... ) >>() );
    }
};

template <class Source, class Target>
struct implicit_cast {
    static void* convertible ( PyObject* obj ) {
        return boost::python::converter::implicit_rvalue_convertible_from_python ( obj,
                boost::python::converter::registered<Source>::converters )
               ? obj : 0;
    }

    static void construct ( PyObject* obj,
                            boost::python::converter::rvalue_from_python_stage1_data* data ) {
        void* storage = ( ( boost::python::converter::rvalue_from_python_storage<Target>* ) data )->storage.bytes;

        boost::python::arg_from_python<Source> get_source ( obj );
        bool convertible = get_source.convertible();
        BOOST_VERIFY ( convertible );

        new ( storage ) Target ( vstd::cast<Target> ( get_source() ) ) ;

        data->convertible = storage;
    }
};

template <class Source, class Target>
void implicitly_convertible_cast ( boost::type<Source>* = 0, boost::type<Target>* = 0 ) {
    typedef implicit_cast<Source,Target> functions;

    boost::python::converter::registry::push_back (
        &functions::convertible
        , &functions::construct
        , boost::python::type_id<Target>()
        , &boost::python::converter::expected_from_python_type_direct<Source>::get_pytype
    );
}
