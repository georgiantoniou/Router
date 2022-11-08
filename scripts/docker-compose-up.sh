#!/bin/bash

cd ~/HDSearch/microsuite
sudo docker compose up &>/dev/null &

sudo docker ps | grep hdsearch
exit_code=`echo $?`

while [ $exit_code -eq 1 ];
do
    sleep 30
    sudo docker ps | grep hdsearch
    exit_code=`echo $?`
done
