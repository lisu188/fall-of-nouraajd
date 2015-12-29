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

    void executeScript ( QString script, boost::python::object nameSpace = boost::python::object() );

    void executeCommand ( std::initializer_list<QString> list );

    QString buildCommand ( std::initializer_list<QString> list );

    void addModule ( QString modName, QString path );

    void addFunction ( QString functionName, QString functionCode, std::initializer_list<QString> args );

    void import ( QString name );

    template<typename Return=void, typename...Args>
    std::function<Return ( Args... ) > getFunction ( QString functionName ) {
        return wrap<Return, Args...>::call ( getObject ( functionName ) );
    }

    template<typename Return=void, typename... Args>
    std::function<Return ( Args... ) > createFunction ( QString functionName, QString functionCode,
            std::initializer_list<QString> args ) {
        vstd::fail_if ( sizeof... ( Args ) != args.size(), "Wrong argument list!" );
        addFunction ( functionName, functionCode, args );
        return getFunction<Return, Args...> ( functionName );
    }

    template<typename Return=void, typename ...Args>
    Return callFunction ( QString name, Args ...params ) {
        return getFunction<Return, Args...> ( name ) ( params... );
    }

    template<typename Return=void, typename ...Args>
    Return callCreatedFunction ( QString functionCode, std::initializer_list<QString> args, Args ...params ) {
        return createFunction<Return, Args...> (
                   "FUNC" + vstd::to_hex_hash<QString> ( functionCode ),
                   functionCode, args ) ( params... );
    }

    template<typename T=boost::python::object>
    T getObject ( QString name ) {
        QString script = "object=";
        script = script.append ( name );
        executeScript ( script );
        boost::python::object object = main_namespace["object"];
        return boost::python::extract<T> ( object );
    }

private:
    boost::python::object main_module;
    boost::python::object main_namespace;
};
