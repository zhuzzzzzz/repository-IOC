#!/bin/bash

# run "./auto-test-for-IocManager.sh create" to test "create" functions of IocManager.
# run "./auto-test-for-IocManager.sh set" to test "set" functions of IocManager.
# run "./auto-test-for-IocManager.sh exec" to test "exec" functions of IocManager.
# run "./auto-test-for-IocManager.sh list" to test "list" functions of IocManager.
# run "./auto-test-for-IocManager.sh all" to test all functions of IocManager.
# set "-v" option for showing details.


PRINT='-p' # '' or '-p'
VERBOSE='' # '' or '-v'
CREATE_TEST='n' # 'y' or 'n'
SET_TEST='n' # 'y' or 'n'
EXEC_TEST='n' # 'y' or 'n'
LIST_TEST='n' # 'y' or 'n'

if [ $# -gt 0 ]; then
    for arg in "$@"; do
        if [ "$arg" == "-v" ]; then
            VERBOSE='-v'
        fi
        if [ "$arg" == "create" ]; then
            CREATE_TEST='y'
        fi
        if [ "$arg" == "set" ]; then
            SET_TEST='y'
        fi
        if [ "$arg" == "exec" ]; then
            EXEC_TEST='y'
        fi
        if [ "$arg" == "list" ]; then
            LIST_TEST='y'
        fi
        if [ "$arg" == "all" ]; then
            CREATE_TEST='y'
            SET_TEST='y'
            EXEC_TEST='y'
            LIST_TEST='y'
        fi
    done
fi

echo_paragraph(){
echo 
echo
echo $1
echo '<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'
echo '---------------------------------------------------------------------------'
echo
echo
}

echo_segment(){
echo '>>>>>>>>>>>>>>>>>'
echo '-----------------'
echo_line $*
}

echo_line(){
echo 
echo $*
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
}


if [ $CREATE_TEST == 'n' -a $SET_TEST == 'n' -a $EXEC_TEST == 'n' -a $LIST_TEST == 'n' ]; then
echo 
echo no function was specified to test!
echo
echo 'run "./auto-test-for-IocManager.sh create" to test "create" functions of IocManager.'
echo 'run "./auto-test-for-IocManager.sh set" to test "set" functions of IocManager.'
echo 'run "./auto-test-for-IocManager.sh exec" to test "exec" functions of IocManager.'
echo 'run "./auto-test-for-IocManager.sh list" to test "list" functions of IocManager.'
echo 'run "./auto-test-for-IocManager.sh all" to test all functions of IocManager.'
echo 'set "-v" option for showing details.'
fi 


if [ $CREATE_TEST == 'y' ]; then
#######
# test for ./IocManager.py create
echo_paragraph 'test for "./IocManager.py create"'

#
string="./IocManager.py create test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

#
string="./IocManager.py create test1 $PRINT $VERBOSE --caputlog --status-ioc --status-os --autosave"
echo_line "$string"
eval $string

#
string="./IocManager.py create test2 $PRINT $VERBOSE --add-asyn"
echo_line "$string"
eval $string

#
string="./IocManager.py create test3 $PRINT $VERBOSE --add-asyn --port-type serial"
echo_line "$string"
eval $string

#
string="./IocManager.py create test4 $PRINT $VERBOSE --add-stream"
echo_line "$string"
eval $string

#
string="./IocManager.py create test5 $PRINT $VERBOSE --add-stream --port-type serial"
echo_line "$string"
eval $string

#
string="./IocManager.py create test6 $PRINT $VERBOSE --add-raw"
echo_line "$string"
eval $string

#
string="./IocManager.py create test7 $PRINT $VERBOSE -f './imtools/template/test/ioc.ini'"
echo_line "$string"
eval $string

#
string="./IocManager.py create test8 $PRINT $VERBOSE -f './imtools/template/test/ioc.ini' --caputlog"
echo_line "$string"
eval $string

#
string="./IocManager.py create test9 $PRINT $VERBOSE -f './imtools/template/test/ioc.ini' -o 'module=abc'"
echo_line "$string"
eval $string

#
string="./IocManager.py create test10 $PRINT $VERBOSE -o ' a = b' 'c = d' -s test"
echo_line "$string"
eval $string

#
string="./IocManager.py remove test test1 test2 test3 test4 test5 test6 test7 test8 test9 test10 -rf $VERBOSE"
echo_line "$string"
eval $string

fi

if [ $SET_TEST == 'y' ]; then
#######
# test for ./IocManager.py set
echo_paragraph 'test for "./IocManager.py set"'

#
string="./IocManager.py create test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE --caputlog --status-ioc --status-os --autosave"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE --add-asyn"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE --add-asyn --port-type serial"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE --add-stream"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE --add-stream --port-type serial"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/ioc.ini'"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/ioc.ini' --caputlog"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/ioc.ini' -o 'module=abc'"
echo_line "$string"
eval $string

#
string="./IocManager.py set test $PRINT $VERBOSE -o ' a = b' 'c = d' -s test"
echo_line "$string"
eval $string

#
string="./IocManager.py remove test -rf $VERBOSE"
echo_line "$string"
eval $string

fi

if [ $EXEC_TEST == 'y' ]; then
#######
# test for ./IocManager.py exec
echo_paragraph 'test for "./IocManager.py exec"'

#
string="./IocManager.py create test0 test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE --add-src-file "
echo_line "$string"
eval $string

#
string="./IocManager.py set test0 test $PRINT $VERBOSE -f './imtools/template/test/ioc.ini'"
echo_line "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE --gen-startup-file"
echo_line "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE --add-src-file --src-path ./imtools/template/test"
echo_line "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE --gen-startup-file; tree ./ioc-repository/test"
echo_line "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE --run-check"
echo_line "$string"
eval $string

#
string="./IocManager.py exec test0 test $VERBOSE -e"
echo_line "$string"
eval $string
echo

#
string="./IocManager.py exec --gen-compose-file --hosts localhost $VERBOSE; tree ../ioc-for-docker; cat ../ioc-for-docker/localhost/compose.yaml"
echo_line "$string"
eval $string

#
mkdir tt
string="./IocManager.py exec test0 test $VERBOSE -e --mount-path ./tt; tree ./tt"
echo_line "$string"
eval $string

string="touch ./tt/ioc-for-docker/localhost/test/log/aaa.log; ./IocManager.py exec test0 test $VERBOSE -e --mount-path ./tt; tree ./tt"
echo_line "$string"
eval $string

string="./IocManager.py exec test0 test $VERBOSE -e --mount-path ./tt --force-overwrite; tree ./tt"
echo_line "$string"
eval $string

#
string="echo sakdkahsd=123 >> ./ioc-repository/test/ioc.ini; cat ./ioc-repository/test/ioc.ini"
echo_line "$string"
eval $string

string="./IocManager.py list"
echo_line "$string"
eval $string

rm -rf ./tt/

#
string="./IocManager.py remove test0 test -rf $VERBOSE"
echo_line "$string"
eval $string

fi

if [ $LIST_TEST == 'y' ]; then
#######
# test for ./IocManager.py list
echo_paragraph 'test for "./IocManager.py list"'

#
string="./IocManager.py create test1 -p --caputlog --status-ioc --status-os --autosave"
eval $string

#
string="./IocManager.py create test2 -p --add-asyn"
eval $string

#
string="./IocManager.py create test3 -p --add-asyn --port-type serial"
eval $string

#
string="./IocManager.py create test4 -p --add-stream"
eval $string

#
string="./IocManager.py create test5 -p --add-stream --port-type serial"
eval $string

#
string="./IocManager.py create test6 -p --add-raw"
eval $string

#
string="./IocManager.py create test7 -p -f './imtools/template/test/ioc.ini'"
eval $string

#
string="./IocManager.py create test8 -p -f './imtools/template/test/ioc.ini' --caputlog"
eval $string

#
string="./IocManager.py create test9 -p -f './imtools/template/test/ioc.ini' -o 'module=abc'"
eval $string

#
string="./IocManager.py create test10 -p -o ' a = b' 'c = d' -s test"
eval $string

#
string="./IocManager.py list $VERBOSE"
echo_segment "$string"
eval $string

#
string="./IocManager.py list 'a = b' -s test $VERBOSE"
echo_line "$string"
eval $string

#
string="./IocManager.py list 'a = c' -s test $VERBOSE"
echo_line "$string"
eval $string

#
string="./IocManager.py list 'module = caputlog' $VERBOSE"
echo_line "$string"
eval $string

#
string="./IocManager.py list 'module = cap' $VERBOSE"
echo_line "$string"
eval $string

#
string="./IocManager.py list 'module = cap' $VERBOSE | xargs ./IocManager.py list 'module = aut' $VERBOSE -l "
echo_line "$string"
eval $string

#
string="./IocManager.py list -s asyn $VERBOSE"
echo_line "$string"
eval $string

#
string="./IocManager.py remove test1 test2 test3 test4 test5 test6 test7 test8 test9 test10 -rf $VERBOSE"
echo_line "$string"
eval $string

fi

#######
# test finished
echo_paragraph 'test finished'
