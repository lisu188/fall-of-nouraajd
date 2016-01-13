#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"



template<typename Return, typename... Args>
struct wrap {
    static std::function<Return ( Args... ) > call ( boost::python::object func ) {
        return [func] ( Args... args ) {
            PY_SAFE_RET (
                boost::python::object ret = func ( args ... );
                boost::python::incref ( ret.ptr() );
                return boost::python::extract<Return> ( ret );
            )
        };
    }
};

template<typename... Args>
struct wrap<void, Args...> {
    static std::function<void ( Args... ) > call ( boost::python::object func ) {
        return [func] ( Args... args ) {
            PY_SAFE ( func ( args ... ); )
        };
    }
};

class CScriptHandler {
public:
    CScriptHandler();

    ~CScriptHandler();

    void execute_script(std::string script, boost::python::object name_space = boost::python::object());

    void execute_command(std::initializer_list<std::string> list);

    std::string build_command(std::initializer_list<std::string> list);

    void add_function(std::string function_name, std::string function_code, std::initializer_list<std::string> args);

    void import ( std::string name );

    template<typename Return=void, typename...Args>
    std::function<Return(Args...)> get_function(std::string functionName) {
        return wrap<Return, Args...>::call(get_object(functionName));
    }

    template<typename Return=void, typename... Args>
    std::function<Return ( Args... ) > createFunction ( std::string functionName, std::string functionCode,
            std::initializer_list<std::string> args ) {
        vstd::fail_if ( sizeof... ( Args ) != args.size(), "Wrong argument list!" );
        add_function(functionName, functionCode, args);
        return get_function<Return, Args...>(functionName);
    }

    template<typename Return=void, typename ...Args>
    Return call_function(std::string name, Args ...params) {
        return get_function<Return, Args...>(name)(params...);
    }

    template<typename Return=void, typename ...Args>
    Return call_created_function(std::string function_code, std::initializer_list<std::string> args, Args ...params) {
        return createFunction<Return, Args...> (
                "FUNC" + vstd::to_hex_hash<std::string>(function_code),
                function_code, args)(params...);
    }

    template<typename T=boost::python::object>
    T get_object(std::string name) {
        std::string script = "object=";
        script = script.append ( name );
        execute_script(script);
        boost::python::object object = main_namespace["object"];
        return boost::python::extract<T> ( object );
    }

private:
    boost::python::object main_module;
    boost::python::object main_namespace;
};
