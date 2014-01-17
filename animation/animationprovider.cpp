#include "animationprovider.h"

#include <animation/animation.h>
#include <sstream>
#include <fstream>
#include <QBitmap>
#include <QDebug>
#include <map/tile.h>
#include <map>

std::map<int, AnimationProvider *> AnimationProvider::instances;

Animation *AnimationProvider::getAnim(std::string path,int size)
{
    path=":/"+path;
    if(instances.find(size)==instances.end())
    {
        instances.insert(std::pair<int, AnimationProvider *>
                         (size,new AnimationProvider(size)));
    }
    return instances.at(size)->getAnimation(path);
}

void AnimationProvider::terminate()
{
    for(std::map<int, AnimationProvider *>::iterator it=instances.begin(); it!=instances.end(); it++)
    {
        delete (*it).second;
    }
    instances.clear();
}

AnimationProvider::AnimationProvider(int size):tileSize(size)
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
        if(!image.hasAlphaChannel()&&path.find("tiles")==std::string::npos) {
            image.setMask(image.createHeuristicMask());
        }
        if(!image.isNull())
        {
            img = new QPixmap(image.scaled(tileSize,tileSize,Qt::IgnoreAspectRatio,Qt::SmoothTransformation));
        }
        else
        {
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
    qDebug() << "Loaded animation:" << path.c_str()<<"\n";
}
