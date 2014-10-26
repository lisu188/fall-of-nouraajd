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
	virtual CGameObject *create ( QString );
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	CTypeHandler();
	CTypeHandler ( const CTypeHandler& );
	virtual CGameObject *create ( QString name ) override;
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	PyTypeHandler();
	PyTypeHandler ( const PyTypeHandler& );
	virtual CGameObject *create ( QString name ) override;
};
