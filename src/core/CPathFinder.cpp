#include "core/CPathFinder.h"

typedef std::function<bool(const Coords &, const Coords &)> Compare;
typedef std::priority_queue<Coords, std::vector<Coords>, Compare> Queue;
typedef std::shared_ptr<std::unordered_map<Coords, int>> Values;

//TODO: implement
//static   void dump ( Values values, Coords start, Coords end ) {
//    int x = 0;
//    int y = 0;
//    double mval = 0;
//    for ( std::pair<Coords, int> val: ( *values ) ) {
//        if ( val.first.x > x ) {
//            x = val.first.x;
//        }
//        if ( val.first.y > y ) {
//            y = val.first.y;
//        }
//        if ( val.second > mval ) {
//            mval = val.second;
//        }
//    }
//    double scale = 256.0 / mval;
//    QImage img ( QSize ( x + 1, y + 1 ), QImage::Format_RGB32 );
//    img.fill ( 0 );
//    for ( std::pair<Coords, int> val: ( *values ) ) {
//        int rgb = val.second * scale;
//        img.setPixel ( val.first.x, val.first.y, qRgb ( rgb, rgb, rgb ) );
//    }
//    std::stringstream stream;
//    stream << "dump/dump" << start.x << "_" << start.y << "_" << end.x << "_" << end.y << ".png";
//    img.save ( std::string::fromStdString ( stream.str() ), "png" );
//}

static Coords getNextStep(const Coords &start, const Coords &goal, Values values) {
    Coords target = start;
    for (Coords coords:NEAR_COORDS (start)) {
        if (vstd::ctn((*values), coords) &&
            ((*values)[coords] < (*values)[target] ||
             ((*values)[coords] == (*values)[target] &&
              coords.getDist(goal) < target.getDist(goal)))) {
            target = coords;
        }
    }
    return target;
}

static Values fillValues(std::function<bool(const Coords &)> canStep,
                         const Coords &goal, const Coords &start) {
    Queue nodes([start](const Coords &a, const Coords &b) {
        double dista = (a.x - start.x) * (a.x - start.x) +
                       (a.y - start.y) * (a.y - start.y);
        double distb = (b.x - start.x) * (b.x - start.x) +
                       (b.y - start.y) * (b.y - start.y);
        return dista > distb;
    });
    std::unordered_set<Coords> marked;
    Values values = std::make_shared<std::unordered_map<Coords, int>>();
    nodes.push(goal);
    (*values)[goal] = 0;

    while (!nodes.empty() && !vstd::ctn(marked, start)) {
        Coords currentCoords = vstd::pop_p(nodes);
        if (marked.insert(currentCoords).second) {
            int curValue = (*values)[currentCoords];
            for (Coords tmpCoords:NEAR_COORDS (currentCoords)) {
                if (canStep(tmpCoords)) {
                    auto it = values->find(tmpCoords);
                    if (it == values->end() || it->second > curValue + 1) {
                        (*values)[tmpCoords] = curValue + 1;
                    }
                    nodes.push(tmpCoords);
                }
            }
        }
    }
    return values;
}

static Values fillAllValues(std::function<bool(const Coords &)> canStep,
                            const Coords &goal) {
    std::unordered_set<Coords> marked;
    Values values = std::make_shared<std::unordered_map<Coords, int>>();
    Queue nodes([values](const Coords &a, const Coords &b) {
        int dista;
        auto it = values->find(a);
        if (it == values->end()) {
            dista = std::numeric_limits<int>::max();
        } else {
            dista = it->second;
        }
        int distb;
        it = values->find(b);
        if (it == values->end()) {
            distb = std::numeric_limits<int>::max();
        } else {
            distb = it->second;
        }
        return dista > distb;
    });
    nodes.push(goal);
    (*values)[goal] = 0;

    while (!nodes.empty()) {
        Coords currentCoords = vstd::pop_p(nodes);
        if (marked.insert(currentCoords).second) {
            int curValue = (*values)[currentCoords];
            for (Coords tmpCoords:NEAR_COORDS (currentCoords)) {
                if (canStep(tmpCoords)) {
                    auto it = values->find(tmpCoords);
                    if (it == values->end() || it->second > curValue + 1) {
                        (*values)[tmpCoords] = curValue + 1;
                    }
                    nodes.push(tmpCoords);
                }
            }
        }
    }
    return values;
}

std::shared_ptr<vstd::future<Coords, void>> CPathFinder::findNextStep(Coords start, Coords goal,
                                                                      std::function<bool(
                                                                              const Coords &)> canStep) {
    return vstd::async([start, goal, canStep]() {
        return getNextStep(start, goal, fillValues(
                canStep, goal, start));
    });
}

std::list<Coords> CPathFinder::findPath(Coords start, Coords goal, std::function<bool(const Coords &)> canStep) {
    std::list<Coords> path;
    Values val = fillValues(canStep, start, goal);
    Coords next = getNextStep(next, goal, val);
    if (next != start) {
        while (next != goal) {
            next = getNextStep(next, goal, val);
            path.push_front(next);
        }
    }
    return path;
}

void CPathFinder::saveMap(Coords start, std::function<bool(const Coords &)> canStep, std::string path) {
    Values values = fillAllValues(canStep, start);
    int minx = std::numeric_limits<int>::max();
    int miny = std::numeric_limits<int>::max();
    int maxx = std::numeric_limits<int>::min();
    int maxy = std::numeric_limits<int>::min();
    int maxVal = std::numeric_limits<int>::min();
    for (std::pair<Coords, int> entry:*values) {
        Coords coords = entry.first;
        if (coords.x < minx) {
            minx = coords.x;
        }
        if (coords.y < miny) {
            miny = coords.y;
        }
        if (coords.x > maxx) {
            maxx = coords.x;
        }
        if (coords.y > maxy) {
            maxy = coords.y;
        }
        if (entry.second > maxVal) {
            maxVal = entry.second;
        }
    }
    int factor = 4;
    SDL_Surface *surface = SDL_CreateRGBSurface(0, factor * (maxx - minx), factor * (maxy - miny), 32, 0, 0, 0, 0);
    float scale = 256.0 / maxVal;
    for (std::pair<Coords, int> entry:*values) {
        int posx = entry.first.x - minx;
        int posy = entry.first.y - miny;
        int val = entry.second;
        SDL_Rect rect;
        rect.x = posx * factor;
        rect.y = posy * factor;
        rect.w = factor;
        rect.h = factor;
        SDL_FillRect(surface, &rect, SDL_MapRGB(surface->format, scale * val, scale * val, scale * val));
    }
    IMG_SavePNG(surface, path.c_str());
}