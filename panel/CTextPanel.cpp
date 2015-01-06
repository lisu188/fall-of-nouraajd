#include "CGamePanel.h"
#include "CGameScene.h"
#include <qpainter.h>
#include <sstream>
#include <QDebug>
#include <qpainter.h>
#include "CGameView.h"
#include "CPlayerView.h"
#include "object/CObject.h"
#include <QBitmap>
#include <QFont>
#include "handler/CHandler.h"

CTextPanel::CTextPanel() {
	this->setZValue ( 7 );
}

CTextPanel::CTextPanel ( const CTextPanel & ) {

}

QRectF CTextPanel::boundingRect() const {
	return QRectF ( 0, 0, 400, 300 );
}

void CTextPanel:: paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) {
	QFont font = painter->font() ;
	painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
	QPen penHText ( QColor ( "WHITE" ) );
	painter->setPen ( penHText );
	painter->drawText ( 0,font.pointSize() ,400,300,Qt::AlignLeft|Qt::TextWordWrap	|Qt::AlignJustify,text );
}

void CTextPanel::showPanel () {
	this->setVisible ( true );
	this->setPos (
	    this->view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
	                             view->height() / 2 - this->boundingRect().height() / 2 ) );
	this->update();
}

void CTextPanel::hidePanel() {
	this->setVisible ( false );
}

void CTextPanel::update() {

}

void CTextPanel::setUpPanel ( CGameView * view ) {
	this->view=view;
}

QString CTextPanel::getText() const {
	return text;
}

void CTextPanel::setText ( const QString &value ) {
	text = value;
}

QString CTextPanel::getPanelName() {
	return "CTextPanel";
}

