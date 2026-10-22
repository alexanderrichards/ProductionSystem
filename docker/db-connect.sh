#!/bin/bash
#
# Connect to the MariaDB database inside the Docker container
#
docker exec -it productionsystem-mariadb mariadb -h localhost -u lzprod -ppassword lzprod
