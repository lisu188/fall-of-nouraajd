#!/bin/bash
echo "C++   $(git ls-files | grep '.h\|.cpp' | xargs cat | wc -l)"
echo "Python$(git ls-files | grep '.py' | xargs cat | wc -l)"
echo "JSON  $(git ls-files | grep '.json' | xargs cat | wc -l)"
