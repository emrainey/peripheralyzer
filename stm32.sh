#!/usr/bin/env bash
set -e  # Exit on error

# It's assumed that you already sourced the virtual environment and set PYTHONPATH before running this script, since it's meant to be called from stm32.sh which handles that setup. If you want to run this script standalone, uncomment the following lines:

declare -a PIDS

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
        echo "  3. Re-run this script to regenerate code with updated names"
        echo ""
        echo "For more info: cat SAFE_NAMING_WORKFLOW.md"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi
}

# cp STM*_name_map.yml ~/Source/embedded-superloop/modules/stm32/scripts
#######################################################################
../svd.sh STM32F407 stm32 f4xx
check_new_entries "STM32F407"
#python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls
mkdir -p out/stm32/f4xx/unified
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 1 --suggested-type GeneralPurposeInputOutput --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 2 --suggested-type SerialPeripheralInterface --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 3 --suggested-type UniversalAsynchronousReceiverTransmitter --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 4 --suggested-type UniversalSynchronousAsynchronousReceiverTransmitter --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 6 --suggested-type InterIntegratedCircuit --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 8 --suggested-type ControllerAreaNetwork --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/f4xx/ymls --unify-group 9 --suggested-type DirectMemoryAccess --unify-dir out/stm32/f4xx/unified &
PIDS+=($!)
# python3 -m peripheralyzer find-duplicates out/stm32/f4xx/unified --report-internal-repeats
for pid in "${PIDS[@]}"; do
    wait "$pid"
done
PIDS=()
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_GeneralPurposeInputOutput.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_SerialPeripheralInterface.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_UniversalAsynchronousReceiverTransmitter.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_UniversalSynchronousAsynchronousReceiverTransmitter.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_InterIntegratedCircuit.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_ControllerAreaNetwork.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/f4xx/unified -o out/stm32/f4xx/cpp -y peripheral_DirectMemoryAccess.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
for pid in "${PIDS[@]}"; do
    wait "$pid"
done
clang-format -Werror -i out/stm32/f4xx/cpp/*.hpp out/stm32/f4xx/cpp/*.cpp
# #######################################################################
../svd.sh STM32H753 stm32 h7xx
check_new_entries "STM32H753"
#python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls
mkdir -p out/stm32/h7xx/unified
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 1 --suggested-type GeneralPurposeInputOutput --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 2 --suggested-type UniversalSynchronousAsynchronousReceiverTransmitter --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 4 --suggested-type SerialPeripheralInterface --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 5 --suggested-type InterIntegratedCircuit --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 11 --suggested-type DirectMemoryAccess --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
python3 -m peripheralyzer find-duplicates out/stm32/h7xx/ymls --unify-group 12 --suggested-type FlexibleDataRateControllerAreaNetwork --unify-dir out/stm32/h7xx/unified &
PIDS+=($!)
for pid in "${PIDS[@]}"; do
    wait "$pid"
done
# python3 -m peripheralyzer find-duplicates out/stm32/h7xx/unified --report-internal-repeats
PIDS=()
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_GeneralPurposeInputOutput.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_UniversalSynchronousAsynchronousReceiverTransmitter.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_SerialPeripheralInterface.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_InterIntegratedCircuit.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_FlexibleDataRateControllerAreaNetwork.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
python3 -m peripheralyzer generate -yr out/stm32/h7xx/unified -o out/stm32/h7xx/cpp -y peripheral_DirectMemoryAccess.yml -t peripheral.hpp.jinja -a &
PIDS+=($!)
for pid in "${PIDS[@]}"; do
    wait "$pid"
done
clang-format -Werror -i out/stm32/h7xx/cpp/*.hpp out/stm32/h7xx/cpp/*.cpp

# Summary of new entries that need renaming
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     BUILD COMPLETE                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if any new entries exist
if [ -f "STM32F407_name_map_new_entries.yml" ] || [ -f "STM32H753_name_map_new_entries.yml" ]; then
    echo "📋 PENDING NAMING UPDATES:"
    echo ""
    [ -f "STM32F407_name_map_new_entries.yml" ] && echo "  • STM32F407_name_map_new_entries.yml (review and rename)"
    [ -f "STM32H753_name_map_new_entries.yml" ] && echo "  • STM32H753_name_map_new_entries.yml (review and rename)"
    echo ""
    echo "📚 Workflow: cat SAFE_NAMING_WORKFLOW.md"
    echo "🔗 Merge: python merge_name_maps.py <device>_name_map.yml --backup"
else
    echo "✓ No new naming entries - all registers have been renamed!"
fi
echo ""