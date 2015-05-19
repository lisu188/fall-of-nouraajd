#pragma once
#include <QString>
#include <QObject>
#include <map>
class CAnimation;
class QPixmap;
class CAnimation :public QObject, private std::map<int, std::pair<QPixmap *, int> > {
    Q_OBJECT
public:
    CAnimation ();
    ~CAnimation();
    QPixmap *getImage();
    int getTime();
    int size();
    void next();
    void add ( QPixmap *img, int time );

private:
    int actual=0;
};
class CAnimationProvider : private std::map<QString, CAnimation *> {
public:
    static CAnimation *getAnim ( QString path );
    virtual ~CAnimationProvider();
private:
    CAnimationProvider ( );
    CAnimation *getAnimation ( QString path );
    void loadAnim ( QString path );
    QPixmap * getImage ( QString path );
};

