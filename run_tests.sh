#!/bin/bash

tests=(
    'tests.test_admin'
    'tests.test_db'
    'tests.test_field'
    'tests.test_meta'
    'tests.test_Migration'
    'tests.test_model'
    'tests.test_package'
    'tests.test_q'
    'tests.test_types'
)

print_chars(){
    local how_many=$1
    local which_char=${2:-=}
    for i in $(seq 1 $how_many);do
        printf "$which_char"
    done
    printf "\n"
}

print_msg(){
    local msg=$1
    local c=$((${#msg}+10))
    echo
    print_chars $c
    echo "==== $msg ===="
    print_chars $c

}

coverage erase
rm -r htmlcov
for test in "${tests[@]}"; do
    cmd="coverage run --source=morm -p -m $test"
    print_msg "$cmd"
    if ! $cmd; then
        exit 1
    fi
    print_msg "mypy -m $test"
    if ! mypy -m "$test"; then
        exit 1
    fi
done

coverage combine
coverage html
