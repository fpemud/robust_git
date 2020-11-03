#!/bin/bash

FILES="python3/robust_git.py"
autopep8 -ia --ignore=E402,E501 ${FILES}
