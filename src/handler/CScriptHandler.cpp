#include "core/CMap.h"

CScriptHandler::CScriptHandler() {
    main_module = boost::python::object(boost::python::handle<>(PyImport_ImportModule("__main__")));
    main_namespace = main_module.attr("__dict__");
    boost::python::incref(main_module.ptr());
}

CScriptHandler::~CScriptHandler() {

}

void CScriptHandler::execute_script(std::string script, boost::python::api::object name_space) {
    const char *string = script.append("\n").c_str();
    if (name_space.is_none()) {
        name_space = main_namespace;
    }
    if (!PyRun_String(string, Py_file_input, name_space.ptr(), name_space.ptr())) {
        boost::python::throw_error_already_set();
    }
}

std::string CScriptHandler::build_command(std::initializer_list<std::string> list) {
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

void CScriptHandler::add_function(std::string function_name, std::string function_code,
                                  std::initializer_list<std::string> args) {
    std::string def = vstd::join({"def ", function_name, "(", vstd::join(args, ","), "):"}, "");
    std::stringstream stream;
    stream << def << std::endl;
    for (std::string line:vstd::split(function_code, '\n')) {
        stream << "\t" << line << std::endl;
    }
    execute_script(stream.str());
}

void CScriptHandler::import(std::string name) {
    execute_script(vstd::join({"import", name}, " "));
}

void CScriptHandler::execute_command(std::initializer_list<std::string> list) {
    execute_script(build_command(list));
}


