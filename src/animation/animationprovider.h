#include "animation.h"

#ifndef ANIMATIONPROVIDER_H
#define ANIMATIONPROVIDER_H

class AnimationProvider : private std::map<std::string, Animation*>
{
public:
    static Animation* getAnim(std::string path, int size);
    static void terminate();

private:
    AnimationProvider(int size);
    ~AnimationProvider();
    Animation * getAnimation(std::string path);

    void loadAnim(std::string path);
    int tileSize;
    static std::map<int, AnimationProvider *> instances;

};

#endif // ANIMATIONPROVIDER_H
