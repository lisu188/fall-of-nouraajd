
#include <QApplication>
#include <QGraphicsPixmapItem>
#include <QGraphicsItemAnimation>
#include <QTimeLine>
#include <QTimer>
#include <QEventLoop>
#include <QDebug>
#include <list>
#include <iostream>
#include <cstring>
class Player;
int entered_count = 0, centered_count = 0, fight_count = 0;
class GameView {
  public:
    void centerOn(Player *) { ++centered_count; }
    void showFightView() { ++fight_count; }
};
class GameScene {
  public:
    static Player *player;
    static GameView *view;
    static Player *getPlayer() { return player; }
    static GameView *getView() { return view; }
};
class Map {
  public:
    static int getTileSize() { return 50; }
    int getCurrentMap() { return 0; }
};
class MapObject : public QObject, public QGraphicsPixmapItem {
  public:
    Map *map = 0;
    int posx = 0, posy = 0, posz = 0;
    bool player_type = false;
    bool inherits(const char *name) const { return player_type && std::strcmp(name, "Player") == 0; }
    int getPosX() const { return posx; }
    int getPosY() const { return posy; }
    int getPosZ() const { return posz; }
    virtual void onEnter() { ++entered_count; }
    void moveTo(int x, int y, int z, bool silent = false);
};
class Player : public MapObject {
  public:
    std::list<MapObject *> entered;
    std::list<int> fights;
    Player() { player_type = true; }
    std::list<MapObject *> *getEntered() { return &entered; }
    std::list<int> *getFightList() { return &fights; }
    void addEntered(MapObject *object) { entered.push_back(object); }
};
Player *GameScene::player = 0;
GameView *GameScene::view = 0;
const int animation_step_ms = 100;

// RECOVERED_FUNCTIONS

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    Map world;
    Player player;
    MapObject event;
    GameView view;
    GameScene::player = &player;
    GameScene::view = &view;
    player.map = &world;
    player.entered.push_back(&event);
    player.fights.push_back(1);
    player.moveTo(1, 0, 0, false);
    if (entered_count != 0)
        return 11;
    QEventLoop loop;
    QTimeLine *timeline = player.findChild<QTimeLine *>();
    if (!timeline)
        return 12;
    QObject::connect(timeline, &QTimeLine::finished, &loop, &QEventLoop::quit);
    QTimer::singleShot(3000, &loop, SLOT(quit()));
    loop.exec();
    std::cout << "{\"entered\":" << entered_count << ",\"remaining\":" << player.entered.size()
              << ",\"centered\":" << centered_count << ",\"fightsShown\":" << fight_count
              << ",\"pixelX\":" << player.QGraphicsItem::pos().x() << "}" << std::endl;
    return entered_count == 1 && player.entered.empty() && centered_count > 0 && fight_count == 1 &&
                   player.QGraphicsItem::pos().x() == 50
               ? 0
               : 10;
}
