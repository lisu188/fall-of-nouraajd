#include "CGamePanel.h"
#include "core/CGame.h"


CFightPanel::CFightPanel() {
    setZValue ( 5 );
    setVisible ( false );
    fightView = std::make_shared<CCreatureFightView>();
    fightView->setParentItem ( this );
}

void CFightPanel::update() {
    if ( view.lock()->getGame()->getMap()->getPlayer() ) {
        fightView->setCreature ( view.lock()->getGame()->getMap()->getPlayer()->getEnemy() );
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

void CFightPanel::showPanel() {
    this->setVisible ( true );
    this->setPos (
        view.lock()->mapToScene ( view.lock()->width() / 2 - this->boundingRect().width() / 2,
                                  view.lock()->height() / 2 - this->boundingRect().height() / 2 ) );
    playerSkillsView->setPos ( 0, this->boundingRect().height() );
    playerSkillsView->setXY (
        this->boundingRect().width() / 50, 1 );
    this->update();
}

void CFightPanel::setUpPanel ( std::shared_ptr<CGameView> view ) {
    this->view = view;
    playerSkillsView = std::make_shared<CPlayerInteractionView> ( this->ptr<CFightPanel>() );
    playerSkillsView->setZValue ( 3 );
    playerSkillsView->setParentItem ( this );
    playerSkillsView->setXY ( 4, 1 );
}

void CFightPanel::hidePanel() {
    this->setVisible ( false );
    fightView->setCreature ( 0 );
    this->update();
}

std::string CFightPanel::getPanelName() {
    return "CFightPanel";
}

CCreatureFightView::CCreatureFightView() {

}

void CCreatureFightView::setCreature ( std::shared_ptr<CCreature> creature ) {
    this->creature = creature;
}

QRectF CCreatureFightView::boundingRect() const {
    return QRectF ( 0, 0, 100, 100 );
}

void CCreatureFightView::paint ( QPainter *painter,
                                 const QStyleOptionGraphicsItem *,
                                 QWidget * ) {
    painter->drawPixmap ( ( boundingRect().width() - creature->boundingRect().width() ) / 2, 0, creature->pixmap() );
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
        std::string::fromStdString ( hpStream.str() ), opt );
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
        std::string::fromStdString ( manaStream.str() ), opt );
}

void CFightPanel::onClickAction ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<CInteraction> interaction = vstd::cast<CInteraction> ( object );
    if ( interaction ) {
        std::shared_ptr<CPlayer> player = interaction->getMap()->getPlayer();
        if ( interaction->getManaCost() <= player->getMana() ) {
            player->setSelectedAction ( interaction );
        }
    }
}