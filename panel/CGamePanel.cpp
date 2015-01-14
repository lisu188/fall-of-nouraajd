#include "CGamePanel.h"


void AGamePanel::handleDrop ( CPlayerView *, CGameObject * ) {
	qFatal ( "No drop handler implemented" );
}

bool AGamePanel::isShown() {
	return this->isVisible();
}


CGameView *AGamePanel::getView() {
	return view;
}


void AGamePanel::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
	this->hidePanel ( );
}


void AGamePanel::setProperty ( QString name, QVariant property ) {
	QByteArray byteArray = name.toUtf8();
	const char* cString = byteArray.constData();
	this->QObject::setProperty ( cString,property );
}


QVariant AGamePanel::property ( QString name ) const {
	QByteArray byteArray = name.toUtf8();
	const char* cString = byteArray.constData();
	return this->QObject::property ( cString );
}


void AGamePanel::setStringProperty ( QString name, QString value ) {
	this->setProperty ( name, value ) ;
}


void AGamePanel::setBoolProperty ( QString name, bool value ) {
	this->setProperty ( name,value );
}


void AGamePanel::setNumericProperty ( QString name, int value ) {
	this->setProperty ( name,value );
}


QString AGamePanel::getStringProperty ( QString name ) const {
	return this->property ( name ).toString();
}


bool AGamePanel::getBoolProperty ( QString name ) const {
	return this->property ( name ).toBool();
}


int AGamePanel::getNumericProperty ( QString name ) const {
	return this->property ( name ).toInt();
}


void AGamePanel::incProperty ( QString name, int value ) {
	this->setNumericProperty ( name,this->getNumericProperty ( name )+value );
}
