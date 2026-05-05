#!/usr/bin/env bash
set -x
set -e
# use the "out" folder for all test output, it will be ignored by git
SVD_FILE=$1
NAMESPACE=$2
FAMILY=$3

if [[ ! -f ${SVD_FILE}.svd ]]; then
    echo "File does not exist: ${SVD_FILE}.svd"
    exit -1
fi

if [[ -z ${NAMESPACE} ]]; then
    echo "Namespace is empty"
    exit -1
fi

OUT=out/${NAMESPACE}/${FAMILY}
if [[ -d ${OUT} ]]; then
    rm -rf ${OUT}
fi
YML_ROOT=${OUT}/ymls
CPP_ROOT=${OUT}/cpp
C_ROOT=${OUT}/c
mkdir -p ${OUT}
python3 transmogrify.py -s ${SVD_FILE}.svd -yr ${YML_ROOT} -ns ${NAMESPACE} -ns ${FAMILY} -nm ${SVD_FILE}_name_map.yml
for yml in `ls -1 ${YML_ROOT}/peripheral_*.yml`; do
    python3 peripheralyzer.py -tr templates -yr ${YML_ROOT} -o ${CPP_ROOT} -y ${yml##*/} -t peripheral.hpp.jinja -t unittest.cpp.jinja -a
    # python3 peripheralyzer.py -tr templates -yr ${YML_ROOT} -o ${C_ROOT} -y ${yml##*/} -t peripheral.h.jinja -t unittest.c.jinja -a
done
clang-format -Werror -i  ${CPP_ROOT}/*.hpp ${CPP_ROOT}/*.cpp
for cpp in `ls -1 ${CPP_ROOT}/*.cpp`; do
    if [[ -f ./${CPP_ROOT}/test ]]; then
        rm ./${CPP_ROOT}/test
    fi
    g++ -std=c++20 -Wall -Werror -Wextra -pedantic -o ${CPP_ROOT}/test -I${CPP_ROOT} ${cpp}
    ./${CPP_ROOT}/test
done
# for c in `ls -1 ${C_ROOT}/*.c`; do
#     if [[ -f ./${C_ROOT}/test ]]; then
#         rm ./${C_ROOT}/test
#     fi
#     gcc -std=c23 -Wall -Werror -Wextra -pedantic -o ${C_ROOT}/test -I${C_ROOT} ${c}
#     ./${C_ROOT}/test
# done
