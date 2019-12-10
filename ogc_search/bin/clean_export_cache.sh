#!/usr/bin/env bash

find "$1" -name '*.csv' -type f -mmin +30 exec rm {}\;