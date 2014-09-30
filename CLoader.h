#pragma once
#include <QString>
#include <boost/python.hpp>

class ALoader;
class ModuleSpec {
public:
	ModuleSpec ( ALoader *loader,std::string name );
	ALoader *loader();
	std::string name;
	std::string subModuleSearch;
	bool hasLocation=true;
	bool cached=false;
private:
	ALoader *scriptLoader=0;
};

class ALoader {
public:
	virtual QString findModule ( QString modName ) =0;

	QString findModule ( std::string modName );

	bool checkModule ( QString modName );

	bool checkModule ( std::string modName );

	void exec_module ( boost::python::object module );

	ModuleSpec *find_spec ( boost::python::object  name,boost::python::object  ,boost::python::object  );

};

class CGeneralLoader :public ALoader {
	virtual QString findModule ( QString modName );
};


