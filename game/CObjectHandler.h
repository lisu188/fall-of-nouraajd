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
	T createMapObject ( QString type ) const {
		return dynamic_cast<T> ( _createMapObject ( type ) );
	}
	void logProperties ( CMapObject *object ) const;
	const QJsonObject *getObjectConfig() const;
private:
	CMapObject *_createMapObject ( QString type ) const;
	void setProperty ( QObject * object , QString key, QJsonValue value ) const;
	QMetaProperty getProperty ( QObject * object ,QString name ) const;
	CMap *map=0;
	QJsonObject objectConfig;
};