function clean_exit(){
    local error_code="$?"
    if test -n "$CEILOMETER_TEST_HBASE_URL"
    then
            python tools/test_hbase_table_utils.py --clear
    fi
    rm -rf "$1"
    kill $(jobs -p)
    return $error_code
}

check_for_cmd () {
    if ! which "$1" >/dev/null 2>&1
    then
        echo "Could not find $1 command" 1>&2
        exit 1
    fi
}

wait_for_line () {
    while read line
    do
        echo "$line" | grep -q "$1" && break
    done < "$2"
    # Read the fifo for ever otherwise process would block
    cat "$2" >/dev/null &
}

