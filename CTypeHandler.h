#pragma once
#include <QObject>
#include <QJsonObject>
#include <QList>
#include "CReflection.h"
class CGameObject;
class ATypeHandler : public QObject {
	Q_OBJECT
public:
	static ATypeHandler* getHandler ( QString name );
	virtual CGameObject *create ( QString ) =0;
	virtual QString getHandlerName() =0;
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
};
