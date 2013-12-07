#include "animation.h"

#ifndef ANIMATIONPROVIDER_H
#define ANIMATIONPROVIDER_H

class AnimationProvider : private std::map<std::string,Animation*>
{
public:
    static Animation* getAnim(std::string path);
    static void terminate();
private:
    AnimationProvider();
    ~AnimationProvider();
    static AnimationProvider *instance;
    Animation * getAnimation(std::string path);

    void loadAnim(std::string path);

};

#endif // ANIMATIONPROVIDER_H
