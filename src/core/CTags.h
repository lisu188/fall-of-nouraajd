#pragma once

class CTags {
public:
    template<typename Range>
    static bool isTagPresent(Range r, std::string tag) {
        for (auto a:r) {
            if (a->hasTag(tag)) {
                return true;
            }
        }
    }
};

