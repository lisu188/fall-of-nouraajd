#pragma once

class CGamePanel : public CGameGraphicsObject {
V_META(CGamePanel, CGameGraphicsObject, vstd::meta::empty())
};

class CGameTextPanel : public CGamePanel {
V_META(CGameTextPanel, CGamePanel, vstd::meta::empty())
};