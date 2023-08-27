#!/usr/bin/env bash
set -x
set -e
# use the "out" folder for all test output, it will be ignored by git
SVD_FILE=$1
NAMESPACE=$2

if [[ ! -f ${SVD_FILE}.svd ]]; then
    echo "File does not exist: ${SVD_FILE}.svd"
    exit -1
fi

if [[ -z ${NAMESPACE} ]]; then
    echo "Namespace is empty"
    exit -1
fi

OUT=out/${NAMESPACE}
mkdir -p ${OUT}
python3 transmogrify.py -s ${SVD_FILE}.svd -yr ${OUT} -ns cmsis -ns ${NAMESPACE} -nm ${SVD_FILE}_name_map.yml
for yml in `ls -1 ${OUT}/peripheral_*.yml`; do
    python3 peripheralyzer.py -tr templates -yr ${OUT} -o ${OUT} -y ${yml##*/} -t peripheral.hpp.jinja -t peripheral.h.jinja -t unittest.cpp.jinja -t unittest.c.jinja -a
done
clang-format -Werror -i  ${OUT}/*.hpp ${OUT}/*.cpp
for cpp in `ls -1 ${OUT}/*.cpp`; do
    if [[ -f ./${OUT}/test ]]; then
        rm ./${OUT}/test
    fi
    g++ -std=c++14 -Wall -Werror -Wextra -pedantic -o ${OUT}/test -I${OUT} ${cpp}
    ./${OUT}/test
done
for c in `ls -1 ${OUT}/*.c`; do
    if [[ -f ./${OUT}/test ]]; then
        rm ./${OUT}/test
    fi
    gcc -std=c17 -Wall -Werror -Wextra -pedantic -o ${OUT}/test -I${OUT} ${c}
    ./${OUT}/test
done


