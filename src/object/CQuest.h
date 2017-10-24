#pragma once

#include "CGameObject.h"

class CQuest : public CGameObject {
V_META(CQuest, CGameObject,   V_PROPERTY(CQuest, std::string, description, getDescription, setDescription))
public:
    CQuest();

    virtual bool isCompleted();

    virtual void onComplete();

    std::string getDescription();

    void setDescription(std::string description);

private:
    std::string description = "";
};


