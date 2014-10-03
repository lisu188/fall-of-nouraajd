#pragma once
#include <QString>
#include <QObject>
#include <boost/python.hpp>
class CMap;
class AScriptLoader;

class ModuleSpec {
public:
	ModuleSpec ( AScriptLoader *loader,std::string name );
	AScriptLoader *loader();
	std::string name;
	std::string subModuleSearch;
	bool hasLocation=true;
	bool cached=false;
private:
	AScriptLoader *scriptLoader=0;
};

class AScriptLoader :public QObject {
	Q_OBJECT
public:
	virtual QString findModule ( QString modName ) =0;
	QString findModule ( std::string modName );
	bool checkModule ( QString modName );
	bool checkModule ( std::string modName );
	void exec_module ( boost::python::object module );
	ModuleSpec *find_spec ( boost::python::object  name,boost::python::object  ,boost::python::object  );
};

class CScriptLoader :public AScriptLoader {
	Q_OBJECT
public:
	virtual QString findModule ( QString modName );
};

class CMapScriptLoader :public AScriptLoader {
	Q_OBJECT
public:
	CMapScriptLoader ( CMap*map );
	virtual QString findModule ( QString modName );
private:
	CMap* map=0;
};


