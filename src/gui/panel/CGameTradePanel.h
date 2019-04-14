#pragma once

#include "object/CPlayer.h"
#include "CGamePanel.h"


class CGameTradePanel : public CGamePanel {
V_META(CGameTradePanel, CGamePanel,
//TODO: unify this with CGameInventoryPanel
       V_PROPERTY(CGameTradePanel, int, xInv, getXInv, setXInv),
       V_PROPERTY(CGameTradePanel, int, yInv, getYInv, setYInv),
       V_PROPERTY(CGameTradePanel, int, selectionBarThickness, getSelectionBarThickness, setSelectionBarThickness),
       V_PROPERTY(CGameTradePanel, std::shared_ptr<CMarket>, market, getMarket, setMarket))

public:
    CGameTradePanel();

    int getXInv();

    void setXInv(int xInv);

    int getYInv();

    void setYInv(int yInv);

    int getSelectionBarThickness();

    void setSelectionBarThickness(int selectionBarThickness);

    std::shared_ptr<CMarket> getMarket();

    void setMarket(std::shared_ptr<CMarket> _market);

private:
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> inventoryView;
    std::shared_ptr<CListView<std::set<std::shared_ptr<CItem>>>> marketView;

    int xInv = 4;
    int yInv = 4;
    int selectionBarThickness = 5;

    std::shared_ptr<CMarket> market;
    std::list<std::weak_ptr<CItem>> selectedInventory;
    std::list<std::weak_ptr<CItem>> selectedMarket;

    void panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) override;

    void panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) override;

    void panelMouseEvent(std::shared_ptr<CGui> shared_ptr, int x, int y) override;

    void drawInventory(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    void drawMarket(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

    bool isInInventory(std::shared_ptr<CGui> x, int y, int i1);

    bool isInMarket(std::shared_ptr<CGui> shared_ptr, int x, int y);

    void handleMarketClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleInventoryClick(std::shared_ptr<CGui> gui, int x, int y);

    void handleEnter(std::shared_ptr<CGui> shared_ptr);

    void selectMarket(std::weak_ptr<CItem> selection);

    void selectInventory(std::weak_ptr<CItem> selection);

    int getTotalSellCost();

    int getTotalBuyCost();
};

