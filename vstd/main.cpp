/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#include "vstd.h"

class CMetaExample {
V_META(CMetaExample,
       vstd::meta::empty,
       V_PROPERTY(CMetaExample, std::string, text, getText, setText))
public:
    CMetaExample() = default;

    std::string getText() {
        return text;
    }

    void setText(std::string text) {
        CMetaExample::text = text;
    }

private:
    std::string text;
};

void vmeta_example() {
    auto example = std::make_shared<CMetaExample>();
    CMetaExample::static_meta()->set_property<CMetaExample, std::string>("text", example, "exampleText");
    vstd::logger::info("Direct access:", example->getText());
    vstd::logger::info("Meta access:",
                       CMetaExample::static_meta()->get_property<CMetaExample, std::string>("text", example));
}

int main() {
    vmeta_example();
    return 0;
}