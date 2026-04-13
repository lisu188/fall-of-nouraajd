# vstd
c++ utility libraries
## vstring
string utilities
## vany
generic object type any utilities over boost:any
## vfunctional
functional programming utilities
## vlazy
lazy initialization template
## vlogger
simple logger for c++
## vmeta
meta object and reflection system for c++
<pre>
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
</pre>
