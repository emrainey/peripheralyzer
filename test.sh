#!/usr/bin/env bash
set -x
set -e
source ../.venv/bin/activate
clear
# use the "out" folder
rm -rf ../out
mkdir -p ../out
PYTHONPATH=../src python3 -m peripheralyzer generate -b -yr ../test -o ../out -y peripheral_test.yml -t peripheral.hpp.jinja -t unittest.cpp.jinja -a -v
clang-format -Werror -i  ../out/*.hpp ../out/*.cpp
g++ -std=c++14 -Wall -Werror -Wextra -pedantic -o ../out/test -I../out ../out/TestPeripheral.cpp
../out/test

