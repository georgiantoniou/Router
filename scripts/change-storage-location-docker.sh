#!/bin/bash

sudo docker rm -f $(docker ps -aq); docker rmi -f $(docker images -q)
sudo systemctl stop docker
umount /var/lib/docker
sudo rm -rf /var/lib/docker
sudo mkdir /var/lib/docker
sudo mkdir /dev/mkdocker
sudo mount --rbind /dev/mkdocker /var/lib/docker
sudo systemctl start docker