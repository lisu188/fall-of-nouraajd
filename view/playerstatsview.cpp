#include "playerstatsview.h"

#include <view/gamescene.h>
#include <qpainter.h>
#include <sstream>
#include <buildings/cave.h>

PlayerStatsView::PlayerStatsView(Player *player)
{
    this->player=player;
    this->setZValue(4);
    update();
}

QRectF PlayerStatsView::boundingRect() const
{
    return QRect(0,0,75,150);
}

void PlayerStatsView::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
    QTextOption opt(Qt::AlignCenter);
    float barx=250;
    float bary=25;

    painter->fillRect(0,0,barx,bary*3,QColor("GREEN"));

    std::ostringstream hpStream;
    hpStream << player->hp;
    hpStream <<"/";
    hpStream << player->hpMax;

    painter->fillRect(0,bary*0,barx*player->getHpRatio()/100.0,bary,QColor("RED"));
    painter->drawText(QRectF(0,bary*0,barx,bary)
                      ,hpStream.str().c_str(),opt);

    std::ostringstream manaStream;
    manaStream << player->mana;
    manaStream <<"/";
    manaStream << player->manaMax;

    painter->fillRect(0,bary*1,barx*player->getManaRatio()/100.0,bary,QColor("BLUE"));
    painter->drawText(QRectF(0,bary*1,barx,bary)
                      ,manaStream.str().c_str(),opt);

    std::ostringstream expStream;
    expStream << player->exp;
    expStream <<"/";
    expStream << (player->level)*(player->level+1)*500;

    painter->fillRect(0,bary*2,barx*player->getExpRatio()/100.0,bary,QColor("YELLOW"));
    painter->drawText(QRectF(0,bary*2,barx,bary)
                      ,expStream.str().c_str(),opt);
}


