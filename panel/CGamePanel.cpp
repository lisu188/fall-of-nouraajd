#include "CGamePanel.h"

AGamePanel::AGamePanel() {
    this->hasTooltip=false;
    this->setVisible ( false );
}

AGamePanel::~AGamePanel() {

}

void AGamePanel::handleDrop ( std::shared_ptr<CPlayerView>, std::shared_ptr<CGameObject>  ) {
    qFatal ( "No drop handler implemented" );
}

bool AGamePanel::isShown() {
    return this->isVisible();
}

std::shared_ptr<CGameView> AGamePanel::getView() {
    return view.lock();
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

void AGamePanel::onClickAction ( std::shared_ptr<CGameObject>  ) {
    this->hidePanel();
}

