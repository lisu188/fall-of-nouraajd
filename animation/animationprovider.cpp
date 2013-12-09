#include "animationprovider.h"

#include <animation/animation.h>
#include <map/tiles/tile.h>
#include <sstream>
#include <fstream>
#include <QBitmap>
#include <QDebug>

AnimationProvider *AnimationProvider::instance=0;

Animation *AnimationProvider::getAnim(std::string path)
{
    if(!instance)
    {
        instance=new AnimationProvider();
    }
    return instance->getAnimation(path);
}

void AnimationProvider::terminate()
{
    delete instance;
}

AnimationProvider::AnimationProvider()
{
}

AnimationProvider::~AnimationProvider()
{
    for(iterator it=begin(); it!=end(); it++)
    {
        delete (*it).second;
    }
    clear();
}

Animation *AnimationProvider::getAnimation(std::string path)
{
    if(this->find(path)!=this->end()) {
        return this->at(path);
    } else if(this->find("assets:/"+path)!=this->end())
    {
        return this->at("assets:/"+path);
    }
    loadAnim(path);
    return getAnimation(path);
}

void AnimationProvider::loadAnim(std::string path)
{
    Animation *anim=new Animation();
    QPixmap *img=0;
    std::map<int,int> timemap;
    std::ifstream time;
    time.open((path+"time.txt").c_str());
    if (time.is_open())
    {
        for (int i=0; !time.eof(); i++)
        {
            int x;
            time >> x;
            timemap.insert(std::pair<int,int>(i,x));
        }
    } else
    {
        timemap.insert(std::pair<int,int>(0,250));
    }
    time.close();
    for(int i=0; true; i++)
    {
        std::string result;
        std::ostringstream convert;
        convert << i;
        result = convert.str();
        QPixmap image((path+result+".png").c_str());
        if(!image.hasAlphaChannel()) {
            image.setMask(image.createHeuristicMask());
        }
        if(!image.isNull())
        {
            img = new QPixmap(image.scaled(Tile::size,Tile::size,Qt::IgnoreAspectRatio,Qt::SmoothTransformation));
        }
        else
        {
            if(anim->size()==0&&path.find("assets:/")==std::string::npos)
            {
                delete anim;
                loadAnim("assets:/"+path);
                return;
            }
            break;
        }
        int frame;
        if(timemap.size()==1) {
            frame=timemap.at(0);
        }
        else {
            frame=timemap.at(i);
        }
        anim->add(img,frame);
    }
    this->insert(std::pair<std::string,Animation*>(path,anim));
    qDebug() << "Loaded animation:" << path.c_str();
}
