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
# Test "rose suite-clean", --only= mode with globs.
#-------------------------------------------------------------------------------
. $(dirname $0)/test_header

run_suite() {
    set -e
    if [[ -n "$JOB_HOST" ]]; then
        rose suite-run --new -q \
            -C "$TEST_SOURCE_DIR/$TEST_KEY_BASE" --name="$NAME" \
            --no-gcontrol -S "HOST=\"$JOB_HOST\"" -- --no-detach --debug
        ssh "$JOB_HOST" "ls -d cylc-run/$NAME 1>/dev/null"
    else
        rose suite-run --new -q \
            -C "$TEST_SOURCE_DIR/$TEST_KEY_BASE" --name="$NAME" \
            --no-gcontrol -- --no-detach --debug
    fi
    ls -d $HOME/cylc-run/$NAME 1>/dev/null
    set +e
}

#-------------------------------------------------------------------------------
N_TESTS=4
tests "$N_TESTS"
#-------------------------------------------------------------------------------
JOB_HOST=$(rose config --default= 't' 'job-host')
if [[ -n $JOB_HOST ]]; then
    JOB_HOST=$(rose host-select -q $JOB_HOST)
fi
#-------------------------------------------------------------------------------
export CYLC_CONF_PATH=
export ROSE_CONF_PATH=
mkdir -p $HOME/cylc-run
SUITE_RUN_DIR=$(mktemp -d --tmpdir=$HOME/cylc-run 'rose-test-battery.XXXXXX')
SUITE_RUN_DIR=$(readlink -f "$SUITE_RUN_DIR")
NAME=$(basename $SUITE_RUN_DIR)
#-------------------------------------------------------------------------------
run_suite
TEST_KEY="$TEST_KEY_BASE-share-tens"
run_pass "$TEST_KEY" \
    rose suite-clean -y -n "$NAME" --only=share/cycle/20?00101T0000Z
LANG=C sort "$TEST_KEY.out" >"$TEST_KEY.sorted.out"
if [[ -n "$JOB_HOST" ]]; then
    # We do not know the relative sort order of $SUITE_RUN_DIR and $JOB_HOST.
    LANG=C sort >"$TEST_KEY.expected.out" <<__OUT__
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20200101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20100101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20000101T0000Z
[INFO] delete: $JOB_HOST:cylc-run/$NAME/share/cycle/20200101T0000Z
[INFO] delete: $JOB_HOST:cylc-run/$NAME/share/cycle/20100101T0000Z
[INFO] delete: $JOB_HOST:cylc-run/$NAME/share/cycle/20000101T0000Z
__OUT__
else
    cat >"$TEST_KEY.expected.out" <<__OUT__
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20000101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20100101T0000Z
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20200101T0000Z
__OUT__
fi
file_cmp "$TEST_KEY.sorted.out" "$TEST_KEY.sorted.out" "$TEST_KEY.expected.out"
TEST_KEY="$TEST_KEY_BASE-multiples"
run_pass "$TEST_KEY" \
    rose suite-clean -y -n "$NAME" \
    --only=share/cycle/*/hello-world.out \
    --only=etc/*/greet-earth.out
if [[ -n "$JOB_HOST" ]]; then
    file_cmp "$TEST_KEY.out" "$TEST_KEY.out" <<__OUT__
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20150101T0000Z/hello-world.out
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20050101T0000Z/hello-world.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20200101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20150101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20100101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20050101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20000101T0000Z/greet-earth.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/share/cycle/20150101T0000Z/hello-world.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/share/cycle/20050101T0000Z/hello-world.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/etc/20200101T0000Z/greet-earth.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/etc/20150101T0000Z/greet-earth.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/etc/20100101T0000Z/greet-earth.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/etc/20050101T0000Z/greet-earth.out
[INFO] delete: $JOB_HOST:cylc-run/$NAME/etc/20000101T0000Z/greet-earth.out
__OUT__
else
    file_cmp "$TEST_KEY.out" "$TEST_KEY.out" <<__OUT__
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20150101T0000Z/hello-world.out
[INFO] delete: localhost:cylc-run/${NAME}/share/cycle/20050101T0000Z/hello-world.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20200101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20150101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20100101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20050101T0000Z/greet-earth.out
[INFO] delete: localhost:cylc-run/${NAME}/etc/20000101T0000Z/greet-earth.out
__OUT__
fi
#-------------------------------------------------------------------------------
rose suite-clean -q -y --name="$NAME"
exit 0
