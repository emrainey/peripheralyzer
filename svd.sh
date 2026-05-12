#!/usr/bin/env bash
set -x
set -e

# It's assumed you already sourced the virtual environment and set PYTHONPATH before running this script, since it's meant to be called from stm32.sh which handles that setup. If you want to run this script standalone

# use the "out" folder for all test output, it will be ignored by git

# Safe Naming Map Mechanism - Check for new entries after processing
check_new_entries() {
    local device=$1
    local new_entries_file="${device}_name_map_new_entries.yml"

    if [ -f "$new_entries_file" ]; then
        local count=$(grep -c "as_type:" "$new_entries_file" 2>/dev/null || echo 0)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✓ New register names discovered: $count entries"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Location: $new_entries_file"
        echo ""
        echo "NEXT STEPS:"
        echo "  1. Review and rename entries in: $new_entries_file"
        echo "  2. Merge when ready: python3 -m peripheralyzer name-map merge ${device}_name_map.yml --backup"
        echo "  3. Re-run to regenerate with updated names"
        echo ""
        echo "For more info: cat SAFE_NAMING_WORKFLOW.md"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi
}

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
mkdir -p ${OUT} ${YML_ROOT} ${CPP_ROOT} ${C_ROOT}
python3 -m peripheralyzer transmogrify -s ${SVD_FILE}.svd -yr ${YML_ROOT} -ns ${NAMESPACE} -ns ${FAMILY} -nm ${SVD_FILE}_name_map.yml
check_new_entries "${SVD_FILE}"
declare -a PIDS
for yml in `ls -1 ${YML_ROOT}/peripheral_*.yml`; do
    # Run in the background
    python3 -m peripheralyzer generate -yr ${YML_ROOT} -o ${CPP_ROOT} -y ${yml##*/} -t peripheral.hpp.jinja -t unittest.cpp.jinja -a &
    PIDS+=($!)
    # python3 peripheralyzer.py -tr templates -yr ${YML_ROOT} -o ${C_ROOT} -y ${yml##*/} -t peripheral.h.jinja -t unittest.c.jinja -a &
    # PIDS+=($!)
done
for pid in "${PIDS[@]}"; do
    wait $pid
done
PIDS=()
clang-format -Werror -i  ${CPP_ROOT}/*.hpp ${CPP_ROOT}/*.cpp
for cpp in `ls -1 ${CPP_ROOT}/*.cpp`; do
    base=$(basename ${cpp} .cpp)
    if [[ -f ./${CPP_ROOT}/${base}_test ]]; then
        rm ./${CPP_ROOT}/${base}_test
    fi
    g++ -std=c++20 -Wall -Werror -Wextra -pedantic -o ${CPP_ROOT}/${base}_test -I${CPP_ROOT} ${cpp} && ./${CPP_ROOT}/${base}_test
done
# for c in `ls -1 ${C_ROOT}/*.c`; do
#     base=$(basename ${c} .c)
#     if [[ -f ./${C_ROOT}/${base}_test ]]; then
#         rm ./${C_ROOT}/${base}_test
#     fi
#     gcc -std=c23 -Wall -Werror -Wextra -pedantic -o ${C_ROOT}/${base}_test -I${C_ROOT} ${c} && ./${C_ROOT}/${base}_test
# done
