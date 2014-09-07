#pragma once
#include <QObject>
#include <QJsonObject>
#include "CTypeHandler.h"
#include "CMapObject.h"
class CMap;
class CObjectHandler : public QObject {
	Q_OBJECT
public:
	CObjectHandler ( CMap *map );
	template<typename T>
	T createMapObject ( QString type ) {
		return dynamic_cast<T> ( _createMapObject ( type ) );
	}
private:
	CMapObject *_createMapObject ( QString type );
	void setProperty ( QObject * object , QString key, QJsonValue value );
	CMap *map;
	QJsonObject objectConfig;
};
