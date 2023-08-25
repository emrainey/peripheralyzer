#!/usr/bin/env bash
set -x
set -e
# use the "out" folder
clear
rm -rf out
mkdir -p out
python3 peripheralyzer.py -b -tr templates -yr test -o out -y peripheral_test.yml -t peripheral.hpp.jinja -t unittest.cpp.jinja -a -v
clang-format -Werror -i  out/*.hpp out/*.cpp
g++ -std=c++14 -o out/test -Iout out/TestPeripheral.cpp
./out/test

