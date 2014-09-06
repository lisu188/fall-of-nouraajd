#pragma once
#include <QObject>
#include <QJsonObject>

class MapObject;
class ATypeHandler : public QObject {
	Q_OBJECT
protected:
	virtual MapObject *create ( QString name ) =0;
	virtual void configure ( MapObject* object ) =0;
	virtual QJsonObject save ( QJsonObject jsonConfig ) =0;
	virtual void load ( MapObject* object ) =0;
};

class CTypeHandler : public ATypeHandler {
	Q_OBJECT
public:
	CTypeHandler();
	CTypeHandler ( const CTypeHandler& );
protected:
	virtual MapObject *create ( QString name );
	virtual void configure ( MapObject *object );
	virtual QJsonObject save ( QJsonObject jsonConfig );
	virtual void load ( MapObject *object );
};
