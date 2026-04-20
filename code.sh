#!/bin/bash

pycodestyle
pylint *.py
flake8 *.py --ignore=

