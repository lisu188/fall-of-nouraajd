#pragma once
#include <QObject>
#include <mutex>
#include <unordered_map>
#include "Util.h"

class CGameObject;
class CObjectHandler;
class ATypeHandler : public QObject {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString ) =0;
	virtual QString getHandlerName() =0;
protected:
	CObjectHandler *getObjectHandler();
};

class CGameObjectConstructor {
public:
	virtual CGameObject *createObject() =0;
};

template<class T>
class CDefaultGameObjectConstructor : public CGameObjectConstructor {
public:
	virtual CGameObject *createObject() override {
		return new T();
	}
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	CTypeHandler();
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
	void registerType ( QString name, CGameObject* ( *constructor ) () );
private:
	std::unordered_map<QString,CGameObject* ( * ) () > constructors;
};

class PyTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	virtual CGameObject *create ( QString name ) override;
	virtual QString getHandlerName() override;
};
