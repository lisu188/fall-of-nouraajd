#pragma once
#include <QObject>
#include <QJsonObject>
#include <QList>
#include "CReflection.h"
class Constructible;
class ATypeHandler : public QObject {
	Q_OBJECT
public:
	static ATypeHandler* getHandler ( QString name );
	ATypeHandler();
	ATypeHandler ( const ATypeHandler& );
	virtual Constructible *create ( QString );
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	CTypeHandler();
	CTypeHandler ( const CTypeHandler& );
	virtual Constructible *create ( QString name ) override;
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	PyTypeHandler();
	PyTypeHandler ( const PyTypeHandler& );
	virtual Constructible *create ( QString name ) override;
};
