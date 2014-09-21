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

void CGuiHandler::refresh() {
	for ( auto it=panels.begin(); it!=panels.end(); it++ ) {
		AGamePanel *panel= ( *it ).second;
		bool vis=panel->isVisible();
		panel->showPanel ();
		panel->setVisible ( vis );
	}
}

void CGuiHandler::initPanels() {
	auto viewList=CReflection::getInstance()->getInherited<AGamePanel*>();
	for ( auto it=viewList.begin(); it!=viewList.end(); it++ ) {
		panels[ ( *it )->metaObject()->className()]=*it;
		map->getScene()->addItem ( *it );
		( *it )->setUpPanel ( map->getScene()->getView() );
		( *it )->setVisible ( false );
	}
}
