#pragma once

#include "core/CGlobal.h"

class CAnimation;

class QPixmap;

class CAnimation : public QObject, private std::map<int, std::pair<std::shared_ptr<QPixmap>, int> > {
Q_OBJECT
public:
    CAnimation();

    ~CAnimation();

    std::shared_ptr<QPixmap> getImage();

    int getTime();

    int size();

    void next();

    void add(std::shared_ptr<QPixmap> img, int time);

private:
    int actual = 0;
};

class CAnimationProvider : private std::map<QString, std::shared_ptr<CAnimation>> {
public:
    static std::shared_ptr<CAnimation> getAnim(QString path);

    virtual ~CAnimationProvider();

private:
    CAnimationProvider();

    std::shared_ptr<CAnimation> getAnimation(QString path);

    void loadAnim(QString path);

    std::shared_ptr<QPixmap> getImage(QString path);
};

