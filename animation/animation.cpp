#include "animation.h"

Animation::Animation()
{
    actual=0;
}

Animation::~Animation()
{
    for(iterator it=begin(); it!=end(); it++)
    {
        delete (*it).second.first;
    }
    clear();
}

QPixmap *Animation::getImage()
{
    return at(actual).first;
}

int Animation::getTime()
{
    if(size()==1) {
        return -1;
    }
    return at(actual).second;
}

int Animation::size()
{
    return std::map<int,std::pair<QPixmap*,int>>::size();
}

void Animation::next()
{
    actual++;
    actual=actual%size();
}

void Animation::add(QPixmap *img, int time)
{
    insert(std::pair<int,std::pair<QPixmap*,int>>(size(),std::pair<QPixmap*,int>(img,time)));
}
