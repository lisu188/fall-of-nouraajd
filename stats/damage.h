#ifndef DAMAGE_H
#define DAMAGE_H

class Damage
{
public:
    Damage();
    int getFire() const;
    void setFire(int value);

    int getThunder() const;
    void setThunder(int value);

    int getFrost() const;
    void setFrost(int value);

    int getNormal() const;
    void setNormal(int value);

    int getShadow() const;
    void setShadow(int value);

private:
    int fire=0;
    int thunder=0;
    int frost=0;
    int normal=0;
    int shadow=0;
};

#endif // DAMAGE_H
