#!/bin/bash

export PYTHONPATH=/mnt/us/python/usr/lib/python2.7/
export LD_LIBRARY_PATH=/mnt/us/python/usr/lib/
export PATH=/mnt/us/python/usr/bin:$PATH

python /mnt/us/mailbook/libupdate.py $*

