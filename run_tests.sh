#!/bin/bash

tests=(
    'tests.test_model'
    'tests.test_field'
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

for test in "${tests[@]}"; do
    print_msg "python -m $test"
    if ! python -m "$test"; then
        exit 1
    fi
    print_msg "mypy -m $test"
    if ! mypy -m "$test"; then
        exit 1
    fi
done
