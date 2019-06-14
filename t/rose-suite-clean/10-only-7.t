#!/bin/bash
#-------------------------------------------------------------------------------
# Copyright (C) 2012-2019 British Crown (Met Office) & Contributors.
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
# Test "rose suite-clean", --only=extglob and a localhost root-dir{*} setting.
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
export CYLC_CONF_PATH=
export ROSE_CONF_PATH=$PWD/conf
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
run_pass "$TEST_KEY" \
    rose suite-clean -y -n "${NAME}" --only='work/!(20100101T0000Z)'
file_cmp  "$TEST_KEY.out" "$TEST_KEY.out" <<__OUT__
[INFO] delete: localhost:cylc-run/${NAME}/work/20200101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/work/20150101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/work/20050101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/work/20000101T0000Z
__OUT__
#-------------------------------------------------------------------------------
rose suite-clean -q -y --name="$NAME"
exit 0