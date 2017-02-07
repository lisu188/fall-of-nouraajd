#pragma once

#include "object/CGameObject.h"
#include "gui/CAnimation.h"

//TODO: think of random offset to desynchronize animations
class CAnimationHandler : public CGameObject {
V_META(CAnimationHandler, CGameObject, vstd::meta::empty())

    std::unordered_map<std::string, std::shared_ptr<CAnimation>> _animations;
public:
    std::shared_ptr<CAnimation> getAnimation(std::string path);

    std::shared_ptr<CAnimation> loadAnimation(std::string path);
};
