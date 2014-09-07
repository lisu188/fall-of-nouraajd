#pragma once
#include <QJsonObject>
#include "Util.h"
#include <QObject>

#include "../gen/prop.h"

class Stats : public QObject {
	Q_OBJECT
	_Stats
public:
	Stats();
	Stats ( const Stats &stats );
    void operator= ( const Stats &stats );
	void setMain ( QString stat );
	int getMain();

	void addBonus ( Stats stats );
	void removeBonus ( Stats stats );

	const char *getText ( int level );
//PROPERTY_ACCESSOR
Q_INVOKABLE void setProperty ( QString name,QVariant property ){
    this->QObject::setProperty(name.toStdString().c_str(),property);
}
Q_INVOKABLE QVariant property ( QString name ) const{
    return this->QObject::property(name.toStdString().c_str());
}
Q_INVOKABLE void setStringProperty ( QString name,QString value ) {
    this->setProperty ( name, value ) ;
}
Q_INVOKABLE void setBoolProperty ( QString name,bool value ) {
    this->setProperty ( name,value );
}
Q_INVOKABLE void setNumericProperty ( QString name,int value ) {
    this->setProperty ( name,value );
}
Q_INVOKABLE QString getStringProperty ( QString name ) const{
    return this->property ( name ).toString();
}
Q_INVOKABLE bool getBoolProperty ( QString name ) const{
    return this->property ( name ).toBool();
}
Q_INVOKABLE int getNumericProperty ( QString name ) const{
    return this->property ( name ).toInt();
}
Q_INVOKABLE void incProperty ( QString name,int value ) {
    this->setNumericProperty ( name,this->getNumericProperty ( name )+value );
}
//!PROPERTY_ACCESSOR
private:
	int *main = 0;
	QString mainS;
};

class Damage : public QObject {
	Q_OBJECT
	_Damage
public:
	Damage();
	Damage ( const Damage &dmg );
    Q_INVOKABLE void setProperty ( QString name,QVariant property ){
        this->QObject::setProperty(name.toStdString().c_str(),property);
    }
    Q_INVOKABLE QVariant property ( QString name ) const{
        return this->QObject::property(name.toStdString().c_str());
    }
    Q_INVOKABLE void setStringProperty ( QString name,QString value ) {
        this->setProperty ( name, value ) ;
    }
    Q_INVOKABLE void setBoolProperty ( QString name,bool value ) {
        this->setProperty ( name,value );
    }
    Q_INVOKABLE void setNumericProperty ( QString name,int value ) {
        this->setProperty ( name,value );
    }
    Q_INVOKABLE QString getStringProperty ( QString name ) const{
        return this->property ( name ).toString();
    }
    Q_INVOKABLE bool getBoolProperty ( QString name ) const{
        return this->property ( name ).toBool();
    }
    Q_INVOKABLE int getNumericProperty ( QString name ) const{
        return this->property ( name ).toInt();
    }
    Q_INVOKABLE void incProperty ( QString name,int value ) {
        this->setNumericProperty ( name,this->getNumericProperty ( name )+value );
    }
};
