#pragma once

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "vstd.h"
#include "vstd.h"

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

    void executeScript ( std::string script, boost::python::object nameSpace = boost::python::object() );

    void executeCommand ( std::initializer_list<std::string> list );

    std::string buildCommand ( std::initializer_list<std::string> list );

    void addModule ( std::string modName, std::string path );

    void addFunction ( std::string functionName, std::string functionCode, std::initializer_list<std::string> args );

    void import ( std::string name );

    template<typename Return=void, typename...Args>
    std::function<Return ( Args... ) > getFunction ( std::string functionName ) {
        return wrap<Return, Args...>::call ( getObject ( functionName ) );
    }

    template<typename Return=void, typename... Args>
    std::function<Return ( Args... ) > createFunction ( std::string functionName, std::string functionCode,
            std::initializer_list<std::string> args ) {
        vstd::fail_if ( sizeof... ( Args ) != args.size(), "Wrong argument list!" );
        addFunction ( functionName, functionCode, args );
        return getFunction<Return, Args...> ( functionName );
    }

    template<typename Return=void, typename ...Args>
    Return callFunction ( std::string name, Args ...params ) {
        return getFunction<Return, Args...> ( name ) ( params... );
    }

    template<typename Return=void, typename ...Args>
    Return callCreatedFunction ( std::string functionCode, std::initializer_list<std::string> args, Args ...params ) {
        return createFunction<Return, Args...> (
                   "FUNC" + vstd::to_hex_hash<std::string> ( functionCode ),
                   functionCode, args ) ( params... );
    }

    template<typename T=boost::python::object>
    T getObject ( std::string name ) {
        std::string script = "object=";
        script = script.append ( name );
        executeScript ( script );
        boost::python::object object = main_namespace["object"];
        return boost::python::extract<T> ( object );
    }

private:
    boost::python::object main_module;
    boost::python::object main_namespace;
};
