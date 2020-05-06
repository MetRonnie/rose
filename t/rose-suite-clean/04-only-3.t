#!/bin/bash
#-------------------------------------------------------------------------------
# Copyright (C) 2012-2020 British Crown (Met Office) & Contributors.
#
# This file is part of Rose, a framework for meteorological suites.
#
# Rose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Rose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Rose. If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test "rose suite-clean", --only= mode and a localhost root-dir{*} setting.
#-------------------------------------------------------------------------------
. $(dirname $0)/test_header

run_suite() {
    set -e
    rose suite-run --new -q \
        -C "$TEST_SOURCE_DIR/$TEST_KEY_BASE" --name="$NAME" \
        --no-gcontrol -- --no-detach --debug
    ls -d $HOME/cylc-run/$NAME 1>/dev/null
    set +e
}

#-------------------------------------------------------------------------------
tests 2
#-------------------------------------------------------------------------------
export ROSE_CONF_PATH=$PWD/conf
export CYLC_CONF_PATH=
export ROOT_DIR_WORK=$PWD/work

mkdir 'conf' 'work'
cat >'conf/rose.conf' <<'__CONF__'
[rose-suite-run]
root-dir{work}=*=$ROOT_DIR_WORK
__CONF__

mkdir -p $HOME/cylc-run
SUITE_RUN_DIR=$(mktemp -d --tmpdir=$HOME/cylc-run 'rose-test-battery.XXXXXX')
SUITE_RUN_DIR=$(readlink -f "$SUITE_RUN_DIR")
NAME=$(basename $SUITE_RUN_DIR)
#-------------------------------------------------------------------------------
run_suite
TEST_KEY="$TEST_KEY_BASE-work"
run_pass "$TEST_KEY" rose suite-clean -y -n "$NAME" --only=work
{
    LANG=C sort <<__OUT__
[INFO] delete: localhost:${ROOT_DIR_WORK}/cylc-run/${NAME}/work
[INFO] delete: localhost:cylc-run/${NAME}/work
__OUT__
} >"${TEST_KEY}.out.expected"
LANG=C sort "${TEST_KEY}.out" >"${TEST_KEY}.out.sorted"
file_cmp  "${TEST_KEY}.out" "${TEST_KEY}.out.sorted" "${TEST_KEY}.out.expected"
#-------------------------------------------------------------------------------
rose suite-clean -q -y --name="$NAME"
exit 0
