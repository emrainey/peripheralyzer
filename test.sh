#!/usr/bin/env bash
set -x
set -e
# use the "out" folder
python3 peripheralyzer.py -b -tr templates -yr test -o out -y peripheral_test.yml -t peripheral.hpp.jinja -t unittest.cpp.jinja -a -v
clang-format -Werror -i  out/*.h out/*.cpp
rm ./out/test
g++ -std=c++14 -o out/test -Iout out/TestPeripheral.cpp
./out/test

