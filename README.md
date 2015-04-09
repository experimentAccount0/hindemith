Hindemith
=========
A Framework for Composing High-Performance Code from Python Descriptions

This project was started by Mike Anderson during his PhD at UC Berkeley
([dissertation link](http://www.eecs.berkeley.edu/Pubs/TechRpts/2014/EECS-2014-210.html)).

[![Build Status](https://travis-ci.org/ucb-sejits/hindemith.svg?branch=master)](https://travis-ci.org/ucb-sejits/hindemith)
[![Coverage Status](https://coveralls.io/repos/ucb-sejits/hindemith/badge.svg?branch=master)](https://coveralls.io/r/ucb-sejits/hindemith?branch=master)


Non-Python Dependencies
-----------------------
clBLAS

```
git clone https://github.com/arrayfire/clBLAS.git
cd clBLAS
mkdir build && cd build
cmake ../src -DCMAKE_BUILD_TYPE=Release -DBUILD_KTEST=OFF
CORES=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || sysctl -n hw.ncpu)
make -j$CORES && sudo make install
```
