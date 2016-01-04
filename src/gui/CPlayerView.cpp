#include "CPlayerView.h"
#include "core/CGame.h"


PlayerStatsView::PlayerStatsView() {
    this->player = player;
    setFixedSize ( 250, 75 );
}

void PlayerStatsView::paintEvent ( QPaintEvent * ) {
    if ( !player ) {
        return;
    }
    QPainter painter;
    painter.begin ( this );
    painter.setRenderHint ( QPainter::Antialiasing );
    QTextOption opt ( Qt::AlignCenter );
    float barx = 250;
    float bary = 25;
    painter.fillRect ( 0, 0, barx, bary * 3, QColor ( "GREEN" ) );
    std::ostringstream hpStream;
    hpStream << player->hp;
    hpStream << "/";
    hpStream << player->hpMax;
    painter.fillRect ( 0, bary * 0, barx * player->getHpRatio() / 100.0, bary,
                       QColor ( "RED" ) );
    painter.drawText ( QRectF ( 0, bary * 0, barx, bary ), hpStream.str().c_str(),
                       opt );
    std::ostringstream manaStream;
    manaStream << player->mana;
    manaStream << "/";
    manaStream << player->manaMax;
    painter.fillRect ( 0, bary * 1, barx * player->getManaRatio() / 100.0, bary,
                       QColor ( "BLUE" ) );
    painter.drawText ( QRectF ( 0, bary * 1, barx, bary ), manaStream.str().c_str(),
                       opt );
    std::ostringstream expStream;
    expStream << player->exp;
    expStream << "/";
    expStream << ( player->level ) * ( player->level + 1 ) * 500;
    painter.fillRect ( 0, bary * 2, barx * player->getExpRatio() / 100.0, bary,
                       QColor ( "YELLOW" ) );
    painter.drawText ( QRectF ( 0, bary * 2, barx, bary ), expStream.str().c_str(),
                       opt );
    painter.end();
}

void PlayerStatsView::setPlayer ( std::shared_ptr<CPlayer> value ) {
    player = value;
    connect ( player.get(), &CPlayer::statsChanged, this, &PlayerStatsView::update );
}

void PlayerStatsView::update() {
    QWidget::update();
}

CListView::CListView ( std::shared_ptr<AGamePanel> panel ) : CPlayerView ( panel ) {
    //to avoid bad pointer exception, defer this until object is initialized
    vstd::call_later ( [this]() {
        right = std::make_shared<CScrollObject> ( this->ptr<CListView>(), true );
        left = std::make_shared<CScrollObject> ( this->ptr<CListView>(), false );
        left->setPos ( 0, y * 50 );
        right->setPos ( ( x - 1 ) * 50, y * 50 );
    } );
    this->setZValue ( 3 );
    curPosition = 0;
    x = 4, y = 4;
    pixmap.load ( CResourcesProvider::getInstance()->getPath ( "images/item.png" ) );
    pixmap = pixmap.scaled ( 50, 50,
                             Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
}

void CListView::update() {
    items = getItems();
    if ( items.size() - x * y < curPosition ) {
        curPosition = items.size() - x * y;
    }
    std::set<QGraphicsItem *> list = vstd::cast<std::set<QGraphicsItem *>> ( childItems() );
    for ( auto childIter = list.begin(); childIter != list.end(); childIter++ ) {
        if ( *childIter == right.get() || *childIter == left.get() ) {
            continue;
        }
        ( *childIter )->setParentItem ( 0 );
        ( *childIter )->setVisible ( false );
    }
    int i = 0;
    for ( auto itemIter = items.begin(); itemIter != items.end(); i++, itemIter++ ) {
        std::shared_ptr<CGameObject> item = *itemIter;
        item->setVisible ( false );
        item->setParentItem ( 0 );
        unsigned int position = i - curPosition;
        if ( position < x * y ) {
            item->setParentItem ( this );
            item->setVisible ( true );
            setNumber ( item, position, x );
        }
    }
    right->setVisible ( items.size() > x * y );
    left->setVisible ( items.size() > x * y );
}

QRectF CListView::boundingRect() const {
    return QRect ( 0, 0, pixmap.size().width() * x,
                   pixmap.size().height() * ( items.size() > x * y ? y + 1 : y ) );
}

void CListView::paint ( QPainter *painter,
                        const QStyleOptionGraphicsItem *,
                        QWidget * ) {
    for ( unsigned int i = 0; i < x; i++ ) {
        for ( unsigned int j = 0; j < y; j++ ) {
            painter->drawPixmap ( i * 50, j * 50,
                                  pixmap );
        }
    }
}

void CListView::updatePosition ( int i ) {
    if ( curPosition == 0 && i < 0 ) {
        return;
    }
    curPosition += i;
    update();
}

void CListView::setXY ( int x, int y ) {
    this->x = x;
    this->y = y;
}

CPlayerView::CPlayerView ( std::shared_ptr<AGamePanel> panel ) : panel ( panel ) {

}

void CPlayerView::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
    const CObjectData *helper = dynamic_cast<const CObjectData *> ( event->mimeData() );
    panel.lock()->handleDrop ( this->ptr<CPlayerView>(), helper->getSource() );
}

CScrollObject::CScrollObject ( std::shared_ptr<CListView> stats, bool isRight ) : stats ( stats ), isRight ( isRight ) {
    this->setZValue ( 1 );
    if ( !isRight ) {
        this->setAnimation ( "images/arrows/left" );
    } else {
        this->setAnimation ( "images/arrows/right" );
    }
    setParentItem ( stats.get() );
}

void CScrollObject::onClickAction ( std::shared_ptr<CGameObject> ) {
    if ( isRight ) {
        stats.lock()->updatePosition ( 1 );
    } else {
        stats.lock()->updatePosition ( -1 );
    }
}

CPlayerEquippedView::CPlayerEquippedView ( std::shared_ptr<AGamePanel> panel ) : CPlayerView ( panel ) {
    for ( unsigned int i = 0; i < 8; i++ ) {
        std::shared_ptr<CItemSlot> slot = std::make_shared<CItemSlot> ( std::string::number ( i ), panel );
        slot->setParentItem ( this );
        slot->setPos ( i % 4 * 50, i / 4 * 50 );
        itemSlots.push_back ( slot );
    }
}

CItemSlot::CItemSlot ( std::string number, std::shared_ptr<AGamePanel> panel ) :
    number ( number ), panel ( panel ) {
    pixmap.load ( CResourcesProvider::getInstance()->getPath ( "images/item.png" ) );
    pixmap = pixmap.scaled ( 50, 50,
                             Qt::IgnoreAspectRatio, Qt::SmoothTransformation );
    this->setAcceptDrops ( true );
}

QRectF CItemSlot::boundingRect() const {
    return QRectF ( 0, 0, 50, 50 );
}

void CItemSlot::paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget * ) {
    painter->drawPixmap ( 0, 0, pixmap );
}

bool CItemSlot::checkType ( std::string slot, std::shared_ptr<CItem> item ) {
    Value config =
        ( *CConfigurationProvider::getConfig (
              "config/slots.json" ) ) [slot].toObject() ["types"].toArray();
    for ( int i = 0; i < config.size(); i++ ) {
        if ( item->inherits ( config[i].toString().toStdString().c_str() ) ) {
            return true;
        }
    }
    return false;
}

void CItemSlot::update() {
    auto player = panel.lock()->getView()->getGame()->getMap()->getPlayer();
    if ( !player ) {
        return;
    }
    auto equipped = player->getEquipped();
    if ( equipped.find ( std::string ( number ) ) != equipped.end() ) {
        std::shared_ptr<CItem> item = equipped.at ( std::string ( number ) );
        if ( item ) {
            item->setParentItem ( this );
            item->setPos ( 0, 0 );
            item->setVisible ( true );
            item->QGraphicsItem::update();
        }
    }
    this->CGameObject::update();
}

std::string CItemSlot::getNumber() {
    return number;
}

void CItemSlot::dragMoveEvent ( QGraphicsSceneDragDropEvent *event ) {
    this->CGameObject::dragMoveEvent ( event );
    const CObjectData *helper = dynamic_cast<const CObjectData *> ( event->mimeData() );
    std::shared_ptr<CItem> item = vstd::cast<CItem> ( helper->getSource() );
    event->setAccepted ( checkType ( number, item ) );
}

void CItemSlot::dropEvent ( QGraphicsSceneDragDropEvent *event ) {
    this->CGameObject::dropEvent ( event );
    const CObjectData *helper = dynamic_cast<const CObjectData *> ( event->mimeData() );
    std::shared_ptr<CItem> item = vstd::cast<CItem> ( helper->getSource() );
    if ( checkType ( number, item ) ) {
        dynamic_cast<CGame *> ( this->scene() )->getMap()->getPlayer()->setItem ( number, item );
    }
    event->acceptProposedAction();
    event->accept();
}


QRectF CPlayerEquippedView::boundingRect() const {
    return QRectF ( 0, 0, 4 * 50, 2 * 50 );
}

void CPlayerEquippedView::paint ( QPainter *,
                                  const QStyleOptionGraphicsItem *,
                                  QWidget * ) { }

void CPlayerEquippedView::update() {
    for ( auto slot:itemSlots ) {
        slot->update();
    }
    this->CGameObject::update();
}

CPlayerInventoryView::CPlayerInventoryView ( std::shared_ptr<AGamePanel> panel ) : CListView ( panel ) {

}

std::set<std::shared_ptr<CGameObject> > CPlayerInventoryView::getItems() const {
    auto player = panel.lock()->getView()->getGame()->getMap()->getPlayer();
    if ( !player ) {
        return std::set<std::shared_ptr<CGameObject>>();
    }
    return vstd::cast<std::set<std::shared_ptr<CGameObject>>> ( player->getInInventory() );
}


CPlayerInteractionView::CPlayerInteractionView ( std::shared_ptr<AGamePanel> panel ) : CListView ( panel ) {

}

std::set<std::shared_ptr<CGameObject> > CPlayerInteractionView::getItems() const {
    auto player = panel.lock()->getView()->getGame()->getMap()->getPlayer();
    if ( !player ) {
        return std::set<std::shared_ptr<CGameObject>>();
    }
    return vstd::cast<std::set<std::shared_ptr<CGameObject>>> ( player->getInteractions() );
}

void CListView::setNumber ( std::shared_ptr<CGameObject> item, int i, int x ) {
    item->setVisible ( true );
    int px = i % x * 50;
    int py = i / x * 50;
    item->setPos ( px, py );
}

CTradeItemsView::CTradeItemsView ( std::shared_ptr<AGamePanel> panel ) : CListView ( panel ) {
}

std::set<std::shared_ptr<CGameObject>> CTradeItemsView::getItems() const {
    std::shared_ptr<CPlayer> player = panel.lock()->getView()->getGame()->getMap()->getPlayer();
    if ( !player || !player->getMarket() ) {
        return std::set<std::shared_ptr<CGameObject>>();
    }
    return vstd::cast<std::set<std::shared_ptr<CGameObject>>> ( player->getMarket()->getTradeItems() );
}
