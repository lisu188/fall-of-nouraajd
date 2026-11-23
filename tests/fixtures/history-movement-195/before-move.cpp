void MapObject::moveTo(int x, int y, int z, bool silent) {
    QPointF from = QGraphicsItem::pos();
    posx = x;
    posy = y;
    posz = z;
    QPointF to(x * Map::getTileSize(), y * Map::getTileSize());
    if (!silent && map && GameScene::getView() && from != to) {
        QGraphicsItemAnimation *animation = new QGraphicsItemAnimation(this);
        QTimeLine *timeline = new QTimeLine(animation_step_ms, animation);
        animation->setItem(this);
        animation->setTimeLine(timeline);
        animation->setPosAt(0, from);
        animation->setPosAt(1, to);
        connect(timeline, &QTimeLine::finished, animation, &QObject::deleteLater);
        timeline->start();
    } else {
        setPos(to);
    }
    if (map)
        QGraphicsItem::setVisible(posz == map->getCurrentMap());
    if (!silent) {
        Player *player = GameScene::getPlayer();
        if (player && player != this && player->getPosX() == posx && player->getPosY() == posy &&
            player->getPosZ() == posz)
            player->addEntered(this);
    }
}
