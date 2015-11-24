function clean_exit(){
    local error_code="$?"
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
    exit_code=1
    while read line
    do
        echo "$line" | grep -q "$1" && exit_code=0 && break
    done < "$2"
    # Read the fifo for ever otherwise process would block
    cat "$2" >/dev/null &
    if [ $exit_code -eq 1 ]; then
        echo "Entries of \"$1\" have not been found. Now tests will be stopped."
        exit $exit_code
    fi
}

