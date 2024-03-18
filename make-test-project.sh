#!/bin/bash

# make-test-project.sh make/del

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

create_host=("hostA" "hostB")
create_num=3


if [ "$1" == 'delete' -o "$1" == 'del' ]; then
	for item in "${create_host[@]}"; do 
		create_prefix=$item
	    	for ((i=1; i<=$create_num; i++)); do
			./IocManager.py remove "$create_prefix$i" -rf
		done
	done
elif [ "$1" == 'create' -o "$1" == 'make' ]; then
	for item in "${create_host[@]}"; do 
		create_prefix=$item
		for ((i=1; i<=$create_num; i++)); do
			echo 
			echo "####### $create_prefix$i #######" 
			# create IOC project
			./IocManager.py create "$create_prefix$i" -f "./imtools/template/test/test.ini"
			# add source files
			./IocManager.py exec "$create_prefix$i" -a --src-path ./imtools/template/test
			# set options
			./IocManager.py set "$create_prefix$i" -s db -o "load_a = ramper.db, name=$create_prefix$i" 
			./IocManager.py set "$create_prefix$i" -o " host = $item "
			# add set options here..
			 
			
			# generate startup files
			./IocManager.py exec "$create_prefix$i" -s
			# copy files to default mount path 
			./IocManager.py exec "$create_prefix$i" -o
			# generate compose files in default mount path 
			./IocManager.py exec -d
		done

		echo 
		echo "####### someting occurs below if IOC run-check failed #######" 
		echo 
		for ((i=1; i<=$create_num; i++)); do
			./IocManager.py exec "$create_prefix$i" -c
		done
	
	done
fi


