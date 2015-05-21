#include "CGamePanel.h"
#include "CGame.h"
#include "gui/CGui.h"
#include "object/CObject.h"
#include "handler/CHandler.h"


CFightPanel::CFightPanel() {
    setZValue ( 5 );
    setVisible ( false );
    fightView =new CCreatureFightView ( this );
    fightView->setParentItem ( this );
}

void CFightPanel::update() {
    if ( this->view->getGame()->getMap()->getPlayer() ) {
        fightView->setCreature ( this->view->getGame()->getMap()->getPlayer()->getEnemy() );
    }
    playerSkillsView->update();
    QGraphicsItem::update();
}

QRectF CFightPanel::boundingRect() const {
    return QRectF ( 0, 0, 400, 300 );
}

void CFightPanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                          QWidget * ) {
    painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
}

void CFightPanel::showPanel (  ) {
    this->setVisible ( true );
    this->setPos (
        view->mapToScene ( view->width() / 2 - this->boundingRect().width() / 2,
                           view->height() / 2 - this->boundingRect().height() / 2 ) );
    playerSkillsView->setPos ( 0, this->boundingRect().height() );
    playerSkillsView->setXY (
        this->boundingRect().width() / 50, 1 );
    this->update();
}

void CFightPanel::setUpPanel ( CGameView *view ) {
    this->view=view;
    playerSkillsView = new CPlayerIteractionView ( this );
    playerSkillsView->setZValue ( 3 );
    playerSkillsView->setParentItem ( this );
    playerSkillsView->setXY ( 4, 1 );
}

void CFightPanel::hidePanel() {
    this->setVisible ( false );
    fightView->setCreature ( 0 );
    this->update();
}

QString CFightPanel::getPanelName() {
    return "CFightPanel";
}

CCreatureFightView::CCreatureFightView ( CFightPanel *panel ) {
    this->setParent ( panel );
    this->setPos ( 0, 0 );
}

void CCreatureFightView::setCreature ( CCreature *creature ) {
    if ( this->creature&&this->creature!=creature ) {
        this->creature->setParentItem ( 0 );
    }
    this->creature = creature;
    if ( creature ) {
        creature->setParentItem ( this );
    }
}

QRectF CCreatureFightView::boundingRect() const {
    return QRectF ( 0, 0, 100, 100 );
}

void CCreatureFightView::paint ( QPainter *painter,
                                 const QStyleOptionGraphicsItem *,
                                 QWidget * ) {
    QGraphicsItem *item = *childItems().begin();
    if ( childItems().size() == 0 ) {
        return;
    }
    item->setPos ( ( ( boundingRect().width() - item->boundingRect().width() ) / 2 ),
                   0 );
    painter->fillRect ( 0, boundingRect().height() - 50, boundingRect().width(), 25,
                        QColor ( "ORANGE" ) );
    painter->fillRect ( 0, boundingRect().height() - 50,
                        boundingRect().width() * creature->getHpRatio() / 100.0, 25,
                        QColor ( "RED" ) );
    QTextOption opt ( Qt::AlignCenter );
    std::ostringstream hpStream;
    hpStream << creature->getHp();
    hpStream << "/";
    hpStream << creature->getHpMax();
    painter->drawText (
        QRectF ( 0, boundingRect().height() - 50, boundingRect().width(), 25 ),
        QString::fromStdString ( hpStream.str() ) , opt );
    painter->fillRect ( 0, boundingRect().height() - 25, boundingRect().width(), 25,
                        QColor ( "CYAN" ) );
    painter->fillRect ( 0, boundingRect().height() - 25,
                        boundingRect().width() * creature->getManaRatio() / 100.0,
                        25, QColor ( "BLUE" ) );
    std::ostringstream manaStream;
    manaStream << creature->getMana();
    manaStream << "/";
    manaStream << creature->getManaMax();
    painter->drawText (
        QRectF ( 0, boundingRect().height() - 25, boundingRect().width(), 25 ),
        QString::fromStdString ( manaStream.str() ), opt );
}

void CFightPanel::onClickAction ( CGameObject *object ) {
    CInteraction *interaction=dynamic_cast<CInteraction*> ( object );
    if ( interaction ) {
        CPlayer *player =interaction->getMap()->getPlayer();
        if ( interaction->getManaCost() > player->getMana() ) {
            return;
        }
        player->setSelectedAction ( interaction );
    }
}