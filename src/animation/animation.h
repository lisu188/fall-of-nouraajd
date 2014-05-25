#include <QPixmap>
#include <map>

#ifndef ANIMATION_H
#define ANIMATION_H

class Animation: private std::map<int, std::pair<QPixmap*, int>>
{
public:
    Animation();
    ~Animation();
    QPixmap *getImage();
    int getTime();
    int size();

    void next();
    void add(QPixmap *img, int time);
private:
    int actual;
};

#endif // ANIMATION_H
