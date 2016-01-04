#pragma once

#include "core/CGlobal.h"

class CAnimation;

class QPixmap;

class CAnimation : public QObject, private std::map<int, std::pair<std::shared_ptr<QPixmap>, int> > {

public:
    CAnimation();

    ~CAnimation();

    std::shared_ptr<QPixmap> getImage();

    int getTime();

    int size();

    void next();

    void add ( std::shared_ptr<QPixmap> img, int time );

private:
    int actual = 0;
};

class CAnimationProvider : private std::map<std::string, std::shared_ptr<CAnimation>> {
public:
    static std::shared_ptr<CAnimation> getAnim ( std::string path );

    virtual ~CAnimationProvider();

private:
    CAnimationProvider();

    std::shared_ptr<CAnimation> getAnimation ( std::string path );

    void loadAnim ( std::string path );

    std::shared_ptr<QPixmap> getImage ( std::string path );
};

