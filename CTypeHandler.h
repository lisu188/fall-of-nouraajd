#pragma once
#include <QObject>
#include <QJsonObject>
#include <QList>
#include "CReflection.h"
class CMapObject;
class ATypeHandler : public QObject {
	Q_OBJECT
public:
	static ATypeHandler* getHandler ( QString name );
	ATypeHandler();
	ATypeHandler ( const ATypeHandler& );
	virtual CMapObject *create ( QString );
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	CTypeHandler();
	CTypeHandler ( const CTypeHandler& );
	virtual CMapObject *create ( QString name );
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	PyTypeHandler();
	PyTypeHandler ( const PyTypeHandler& );
	virtual CMapObject *create ( QString name );
};
