#include "CGuiHandler.h"
#include "CMap.h"
#include "CGamePanel.h"
#include "CGameScene.h"

CGuiHandler::CGuiHandler ( CMap *map ) :QObject ( map ) {
	this->map=map;
	initPanels();
}

void CGuiHandler::showMessage ( QString msg ) {
	AGamePanel *panel=getPanel ( "CTextPanel" );
	panel->setStringProperty ( "text",msg );
	panel->showPanel();
}

AGamePanel *CGuiHandler::getPanel ( QString panel ) {
	return panels[panel];
}

bool CGuiHandler::isAnyPanelVisible() {
    for ( auto it:panels) {
        if ( it .second->isShown() ) {
			return true;
		}
	}
	return false;
}

void CGuiHandler::refresh() {
    for ( auto it:panels) {
        AGamePanel *panel= it.second;
		panel->update();
	}
}

void CGuiHandler::initPanels() {
	auto viewList=CReflection::getInstance()->getInherited<AGamePanel*>();
    for ( auto it:viewList ) {
        panels[ it ->metaObject()->className()]=it;
        map->getScene()->addItem (it );
        it ->setUpPanel ( map->getScene()->getView() );
        it ->hidePanel ( );
        qDebug() <<"Initialized panel:"<<  it->metaObject()->className() <<"\n";
    }
}
