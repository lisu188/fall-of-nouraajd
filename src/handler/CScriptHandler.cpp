#include "core/CMap.h"
#include "scripting/CScripting.h"

static const char *START_SCRIPT = "import sys\n"
        "from _core import CScriptLoader\n"
        "sys.path=[]\n"
        "sys.meta_path.append(CScriptLoader())\n"
        "sys.dont_write_bytecode=True";

CScriptHandler::CScriptHandler() {
    PyImport_AppendInittab("_game", PyInit__game);
    PyImport_AppendInittab("_core", PyInit__core);
#ifdef DEBUG_MODE
    PyImport_AppendInittab ( "debug",PyInit_debug );
#endif
    Py_Initialize();
    vstd::logger::debug("Initialized python interpreter.", "\n");
    main_module = boost::python::object(boost::python::handle<>(PyImport_ImportModule("__main__")));
    main_namespace = main_module.attr("__dict__");
    boost::python::incref(main_module.ptr());
    vstd::logger::debug("Imported main module.", "\n");
    executeScript(START_SCRIPT);
    vstd::logger::debug("Executed starting scripts.", "\n");
}

CScriptHandler::~CScriptHandler() {
    Py_Finalize();
}

void CScriptHandler::executeScript(std::string script, boost::python::api::object nameSpace) {
    if (nameSpace.is_none()) {
        boost::python::exec(script.append("\n").c_str(), main_namespace);
    } else {
        boost::python::exec(script.append("\n").c_str(), nameSpace);
    }
}

std::string CScriptHandler::buildCommand(std::initializer_list<std::string> list) {
    std::string command;
    unsigned int pos = 0;
    for (auto it = list.begin(); it != list.end(); it++, pos++) {
        std::string part = vstd::replace(*it, "\"", "\\\"");
        if (pos == 0) {
            command.append(part);
            command.append("(");
        } else {
            command.append("\"");
            command.append(part);
            command.append("\"");
            if (pos < list.size() - 1) {
                command.append(",");
            } else {
                command.append(")");
            }
        }
    }
    return command;
}

void CScriptHandler::addModule(std::string modName, std::string path) {
    std::shared_ptr<CCustomScriptLoader> loader = std::make_shared<CCustomScriptLoader>(modName, path);
    callFunction("sys.meta_path.append", loader);
    executeScript(vstd::join({"import", modName}, " "));
    callFunction("sys.meta_path.remove", loader);
}

void CScriptHandler::addFunction(std::string functionName, std::string functionCode,
                                 std::initializer_list<std::string> args) {
    std::string def = vstd::join({"def ", functionName, "(", vstd::join(args, ","), "):"}, "");
    std::stringstream stream;
    stream << def << std::endl;
    for (std::string line:vstd::split(functionCode, '\n')) {
        stream << "\t" << line << std::endl;
    }
    executeScript(stream.str());
}

void CScriptHandler::import(std::string name) {
    executeScript(vstd::join({"import", name}, " "));
}

void CScriptHandler::executeCommand(std::initializer_list<std::string> list) {
    executeScript(buildCommand(list));
}


