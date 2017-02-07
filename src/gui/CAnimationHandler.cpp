
#include "CAnimationHandler.h"

std::shared_ptr<CAnimation> CAnimationHandler::getAnimation(std::string path) {
    auto anim = _animations.find(path);
    if (anim == _animations.end()) {
        _animations[path] = this->loadAnimation(path);
        return getAnimation(path);
    }
    return _animations[path];
}

std::shared_ptr<CAnimation> CAnimationHandler::loadAnimation(std::string path) {
    if (boost::filesystem::is_directory(path)) {
        return std::make_shared<CDynamicAnimation>(path);
    } else if (boost::filesystem::is_regular_file(path)) {
        return std::make_shared<CStaticAnimation>(path);
    } else {
        vstd::logger::fatal("wtf!");//TODO:
    }
}
