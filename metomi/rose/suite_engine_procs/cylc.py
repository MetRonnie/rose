# Copyright (C) British Crown (Met Office) & Contributors.
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
# -----------------------------------------------------------------------------
"""Logic specific to the Cylc suite engine."""

from glob import glob
import os
import pwd
import re
from random import shuffle
import socket
import sqlite3
import tarfile
from time import sleep
from uuid import uuid4

from metomi.rose.fs_util import FileSystemEvent
from metomi.rose.popen import RosePopenError
from metomi.rose.reporter import Reporter
from metomi.rose.suite_engine_proc import (
    SuiteEngineProcessor,
    TaskProps
)


class CylcProcessor(SuiteEngineProcessor):

    """Logic specific to the cylc suite engine."""

    REC_CYCLE_TIME = re.compile(
        r"\A[\+\-]?\d+(?:W\d+)?(?:T\d+(?:Z|[+-]\d+)?)?\Z")  # Good enough?
    SCHEME = "cylc"
    SUITE_CONF = "flow.cylc"
    SUITE_NAME_ENV = "CYLC_SUITE_NAME"
    SUITE_DIR_REL_ROOT = "cylc-run"
    TASK_ID_DELIM = "."

    TIMEOUT = 60  # seconds

    def __init__(self, *args, **kwargs):
        SuiteEngineProcessor.__init__(self, *args, **kwargs)
        self.daos = {}
        self.host = None
        self.user = None

    @classmethod
    def get_suite_dir_rel(cls, suite_name, *paths):
        """Return the relative path to the suite running directory.

        paths -- if specified, are added to the end of the path.

        """
        return os.path.join(cls.SUITE_DIR_REL_ROOT, suite_name, *paths)

    def get_suite_jobs_auths(self, suite_name, cycle_name_tuples=None):
        """Return remote ["[user@]host", ...] for submitted jobs."""
        # TODO: reimplement for Cylc8?
        # https://github.com/metomi/rose/issues/2445
        self.handle_event(
            Exception(
                'WARNING: Rose cannot currently inspect the platform a Cylc'
                ' task has or will run on.\n'
                ' https://github.com/metomi/rose/issues/2445'
            )
        )
        return []

    def get_task_auth(self, suite_name, task_name):
        """Return [user@]host for a remote task in a suite.

        Or None if task does not run remotely.

        """
        # TODO: reimplement for Cylc8?
        # https://github.com/metomi/rose/issues/2445
        self.handle_event(
            Exception(
                'WARNING: Rose cannot currently inspect the platform a Cylc'
                ' task has or will run on.\n'
                ' https://github.com/metomi/rose/issues/2445'
            )
        )
        return None

    def get_task_props_from_env(self):
        """Get attributes of a suite task from environment variables.

        Return a TaskProps object containing the attributes of a suite task.

        """

        suite_name = os.environ[self.SUITE_NAME_ENV]
        suite_dir_rel = self.get_suite_dir_rel(suite_name)
        suite_dir = self.get_suite_dir(suite_name)
        task_id = os.environ["CYLC_TASK_ID"]
        task_name = os.environ["CYLC_TASK_NAME"]
        task_cycle_time = os.environ["CYLC_TASK_CYCLE_POINT"]
        cycling_mode = os.environ.get("CYLC_CYCLING_MODE", "gregorian")
        if task_cycle_time == "1" and not cycling_mode == "integer":
            task_cycle_time = None
        task_log_root = os.environ["CYLC_TASK_LOG_ROOT"]
        task_is_cold_start = "false"
        if os.environ.get("CYLC_TASK_IS_COLDSTART", "True") == "True":
            task_is_cold_start = "true"

        return TaskProps(suite_name=suite_name,
                         suite_dir_rel=suite_dir_rel,
                         suite_dir=suite_dir,
                         task_id=task_id,
                         task_name=task_name,
                         task_cycle_time=task_cycle_time,
                         task_log_dir=os.path.dirname(task_log_root),
                         task_log_root=task_log_root,
                         task_is_cold_start=task_is_cold_start,
                         cycling_mode=cycling_mode)

    def job_logs_archive(self, suite_name, items):
        """Archive cycle job logs.

        suite_name -- The name of a suite.
        items -- A list of relevant items.

        """
        cycles = []
        if "*" in items:
            stmt = "SELECT DISTINCT cycle FROM task_jobs"
            for row in self._db_exec(suite_name, stmt):
                cycles.append(row[0])
            self._db_close(suite_name)
        else:
            for item in items:
                cycle = self._parse_task_cycle_id(item)[0]
                if cycle:
                    cycles.append(cycle)
        self.job_logs_pull_remote(suite_name, cycles, prune_remote_mode=True)
        cwd = os.getcwd()
        self.fs_util.chdir(self.get_suite_dir(suite_name))
        try:
            for cycle in cycles:
                archive_file_name0 = os.path.join("log",
                                                  "job-" + cycle + ".tar")
                archive_file_name = archive_file_name0 + ".gz"
                if os.path.exists(archive_file_name):
                    continue
                glob_ = os.path.join(cycle, "*", "*", "*")
                names = glob(os.path.join("log", "job", glob_))
                if not names:
                    continue
                f_bsize = os.statvfs(".").f_bsize
                tar = tarfile.open(archive_file_name0, "w", bufsize=f_bsize)
                for name in names:
                    cycle, _, s_n, ext = self.parse_job_log_rel_path(name)
                    if s_n == "NN" or ext == "job.status":
                        continue
                    tar.add(name, name.replace("log/", "", 1))
                tar.close()
                # N.B. Python's gzip is slow
                self.popen.run_simple("gzip", "-f", archive_file_name0)
                self.handle_event(FileSystemEvent(FileSystemEvent.CREATE,
                                                  archive_file_name))
                self.fs_util.delete(os.path.join("log", "job", cycle))
        finally:
            try:
                self.fs_util.chdir(cwd)
            except OSError:
                pass

    def job_logs_pull_remote(self, suite_name, items,
                             prune_remote_mode=False, force_mode=False):
        """Pull and housekeep the job logs on remote task hosts.

        suite_name -- The name of a suite.
        items -- A list of relevant items.
        prune_remote_mode -- Remove remote job logs after pulling them.
        force_mode -- Pull even if "job.out" already exists.

        """
        # Pull from remote.
        # Create a file with a uuid name, so system knows to do nothing on
        # shared file systems.
        uuid = str(uuid4())
        log_dir_rel = self.get_suite_dir_rel(suite_name, "log", "job")
        log_dir = os.path.join(os.path.expanduser("~"), log_dir_rel)
        uuid_file_name = os.path.join(log_dir, uuid)
        self.fs_util.touch(uuid_file_name)
        try:
            auths_filters = []  # [(auths, includes, excludes), ...]
            if "*" in items:
                auths = self.get_suite_jobs_auths(suite_name)
                if auths:
                    # A shuffle here should allow the load for doing "rm -rf"
                    # to be shared between job hosts who share a file system.
                    shuffle(auths)
                    auths_filters.append((auths, [], []))
            else:
                for item in items:
                    cycle, name = self._parse_task_cycle_id(item)
                    if cycle is not None:
                        arch_f_name = "job-" + cycle + ".tar.gz"
                        if os.path.exists(arch_f_name):
                            continue
                    # Don't bother if "job.out" already exists
                    # Unless forced to do so
                    if (cycle is not None and name is not None and
                            not prune_remote_mode and not force_mode and
                            os.path.exists(os.path.join(
                                log_dir, str(cycle), name, "NN", "job.out"))):
                        continue
                    auths = self.get_suite_jobs_auths(
                        suite_name, [(cycle, name)])
                    if auths:
                        # A shuffle here should allow the load for doing "rm
                        # -rf" to be shared between job hosts who share a file
                        # system.
                        shuffle(auths)
                        includes = []
                        excludes = []
                        if cycle is None and name is None:
                            includes = []
                            excludes = []
                        elif name is None:
                            includes = ["/" + cycle]
                            excludes = ["/*"]
                        elif cycle is None:
                            includes = ["/*/" + name]
                            excludes = ["/*/*"]
                        else:
                            includes = ["/" + cycle, "/" + cycle + "/" + name]
                            excludes = ["/*", "/*/*"]
                        auths_filters.append((auths, includes, excludes))

            for auths, includes, excludes in auths_filters:
                for auth in auths:
                    data = {"auth": auth,
                            "log_dir_rel": log_dir_rel,
                            "uuid": uuid,
                            "glob_": "*"}
                    if includes:
                        data["glob_"] = includes[-1][1:]  # Remove leading /
                    cmd = self.popen.get_cmd(
                        "ssh", auth,
                        ("cd %(log_dir_rel)s && " +
                         "(! test -f %(uuid)s && ls -d %(glob_)s)") % data)
                    ret_code, ssh_ls_out, _ = self.popen.run(*cmd)
                    if ret_code:
                        continue
                    cmd_list = ["rsync"]
                    for include in includes:
                        cmd_list.append("--include=" + include)
                    for exclude in excludes:
                        cmd_list.append("--exclude=" + exclude)
                    cmd_list.append("%(auth)s:%(log_dir_rel)s/" % data)
                    cmd_list.append(log_dir)
                    try:
                        cmd = self.popen.get_cmd(*cmd_list)
                        self.popen(*cmd)
                    except RosePopenError as exc:
                        self.handle_event(exc, level=Reporter.WARN)
                    if not prune_remote_mode:
                        continue
                    try:
                        cmd = self.popen.get_cmd(
                            "ssh", auth,
                            "cd %(log_dir_rel)s && rm -fr %(glob_)s" % data)
                        self.popen(*cmd)
                    except RosePopenError as exc:
                        self.handle_event(exc, level=Reporter.WARN)
                    else:
                        for line in sorted(ssh_ls_out.splitlines()):
                            event = FileSystemEvent(
                                FileSystemEvent.DELETE,
                                "%s:log/job/%s/" % (auth, line))
                            self.handle_event(event)
        finally:
            self.fs_util.delete(uuid_file_name)

    def job_logs_remove_on_server(self, suite_name, items):
        """Remove cycle job logs.

        suite_name -- The name of a suite.
        items -- A list of relevant items.

        """
        cycles = []
        if "*" in items:
            stmt = "SELECT DISTINCT cycle FROM task_jobs"
            for row in self._db_exec(suite_name, stmt):
                cycles.append(row[0])
            self._db_close(suite_name)
        else:
            for item in items:
                cycle = self._parse_task_cycle_id(item)[0]
                if cycle:
                    cycles.append(cycle)

        cwd = os.getcwd()
        self.fs_util.chdir(self.get_suite_dir(suite_name))
        try:
            for cycle in cycles:
                # tar.gz files
                archive_file_name = os.path.join("log",
                                                 "job-" + cycle + ".tar.gz")
                if os.path.exists(archive_file_name):
                    self.fs_util.delete(archive_file_name)
                # cycle directories
                dir_name_prefix = os.path.join("log", "job")
                dir_name = os.path.join(dir_name_prefix, cycle)
                if os.path.exists(dir_name):
                    self.fs_util.delete(dir_name)
        finally:
            try:
                self.fs_util.chdir(cwd)
            except OSError:
                pass

    @classmethod
    def parse_job_log_rel_path(cls, f_name):
        """Return (cycle, task, submit_num, ext)."""
        return f_name.replace("log/job/", "").split("/", 3)

    def _db_close(self, suite_name):
        """Close a named database connection."""
        if self.daos.get(suite_name) is not None:
            self.daos[suite_name].close()

    def _db_exec(self, suite_name, stmt, stmt_args=None):
        """Execute a query on a named database connection."""
        daos = self._db_init(suite_name)
        return daos.execute(stmt, stmt_args)

    def _db_init(self, suite_name):
        """Initialise a named database connection."""
        if suite_name not in self.daos:
            prefix = "~"
            db_f_name = os.path.expanduser(os.path.join(
                prefix, self.get_suite_dir_rel(suite_name, "log", "db")))
            self.daos[suite_name] = CylcSuiteDAO(db_f_name)
        return self.daos[suite_name]

    def _parse_task_cycle_id(self, item):
        """Parse name.cycle. Return (cycle, name)."""
        cycle, name = None, None
        if self.REC_CYCLE_TIME.match(item):
            cycle = item
        elif self.TASK_ID_DELIM in item:
            name, cycle = item.split(self.TASK_ID_DELIM, 1)
        else:
            name = item
        return (cycle, name)

    def _parse_user_host(self, auth=None, user=None, host=None):
        """Parse user@host. Return normalised [user@]host string."""
        if self.user is None:
            self.user = pwd.getpwuid(os.getuid()).pw_name
        if self.host is None:
            self.host = socket.gethostname()
        if auth is not None:
            user = None
            host = auth
            if "@" in auth:
                user, host = auth.split("@", 1)
        user, host = [
            i.decode() if isinstance(i, bytes) else i for i in [user, host]]
        if user in ["None", self.user]:
            user = None
        if host and ("`" in host or "$" in host):
            command = ["bash", "-ec", "H=" + host + "; echo $H"]
            host = self.popen(*command)[0].strip().decode()
        if (host in ["None", self.host] or
                self.host_selector.is_local_host(host)):
            host = None
        if user and host:
            auth = user + "@" + host
        elif user:
            auth = user + "@" + self.host
        elif host:
            auth = host
        else:
            auth = None
        return auth


class CylcSuiteDAO:

    """Generic SQLite Data Access Object."""

    CONNECT_RETRY_DELAY = 0.1
    N_CONNECT_TRIES = 10

    def __init__(self, db_f_name):
        self.db_f_name = db_f_name
        self.conn = None
        self.cursor = None

    def close(self):
        """Close the DB connection."""
        if self.conn is not None:
            try:
                self.conn.close()
            except (sqlite3.OperationalError, sqlite3.ProgrammingError):
                pass
        self.cursor = None
        self.conn = None

    def connect(self, is_new=False):
        """Connect to the DB. Set the cursor. Return the connection."""
        if self.cursor is not None:
            return self.cursor
        if not is_new and not os.access(self.db_f_name, os.F_OK | os.R_OK):
            return None
        for _ in range(self.N_CONNECT_TRIES):
            try:
                self.conn = sqlite3.connect(
                    self.db_f_name, self.CONNECT_RETRY_DELAY)
                self.cursor = self.conn.cursor()
            except sqlite3.OperationalError:
                sleep(self.CONNECT_RETRY_DELAY)
                self.conn = None
                self.cursor = None
            else:
                break
        return self.conn

    def execute(self, stmt, stmt_args=None):
        """Execute a statement. Return the cursor."""
        if stmt_args is None:
            stmt_args = []
        for _ in range(self.N_CONNECT_TRIES):
            if self.connect() is None:
                return []
            try:
                self.cursor.execute(stmt, stmt_args)
            except sqlite3.OperationalError:
                sleep(self.CONNECT_RETRY_DELAY)
                self.conn = None
                self.cursor = None
            except sqlite3.ProgrammingError:
                self.conn = None
                self.cursor = None
            else:
                break
        if self.cursor is None:
            return []
        return self.cursor
