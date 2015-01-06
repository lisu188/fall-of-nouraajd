#include "handler/CHandler.h"
#include "CMap.h"
#include "panel/CPanel.h"
#include "CGameScene.h"
#include <QDebug>

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

void CGuiHandler::showPanel ( QString panel ) {
	panels[panel]->showPanel();
}

void CGuiHandler::flipPanel ( QString panelName ) {
	AGamePanel *panel=getPanel ( panelName );
	if ( panel->isShown() ) {
		panel->hidePanel();
	} else {
		panel->showPanel();
	}
}

bool CGuiHandler::isAnyPanelVisible() {
	for ( auto it:panels ) {
		if ( it .second->isShown() ) {
			return true;
		}
	}
	return false;
}

void CGuiHandler::refresh() {
	for ( auto it:panels ) {
		AGamePanel *panel= it.second;
		if ( panel->isShown() ) {
			panel->update();
		}
	}
}

void CGuiHandler::initPanels() {
	std::list<AGamePanel*> viewList {new CFightPanel(),new CCharPanel(),new CTextPanel(),new CTradePanel() };
	for ( AGamePanel* it:viewList ) {
		panels[it->getPanelName()]=it;
		map->getScene()->addItem ( it );
		it ->setUpPanel ( map->getScene()->getView() );
		it ->hidePanel ( );
		qDebug() <<"Initialized panel:"<<  it->metaObject()->className() <<"\n";
	}
}
