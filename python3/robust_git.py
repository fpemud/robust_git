#!/usr/bin/env python3

# robust_git.py - robust git operations
#
# Copyright (c) 2019-2020 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
robust_git

@author: Fpemud
@license: GPLv3 License
@contact: fpemud@sina.com
"""

import os
import sys
import time
import shutil
import selectors
import subprocess

__author__ = "fpemud@sina.com (Fpemud)"
__version__ = "0.0.1"


def clone(*args):
    args = list(args)
    while True:
        try:
            _Util.shellExecWithStuckCheck(["/usr/bin/git", "clone"] + args, _Util.getGitSpeedEnv())
            break
        except _ProcessStuckError:
            time.sleep(_RETRY_TIMEOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode > 128:
                # terminated by signal, no retry needed
                raise
            time.sleep(_RETRY_TIMEOUT)


def pull(*args):
    args = list(args)
    assert not any(x not in args for x in ["-r", "--rebase", "--no-rebase"])

    while True:
        try:
            _Util.shellExecWithStuckCheck(["/usr/bin/git", "pull", "--rebase"] + args, _Util.getGitSpeedEnv())
            break
        except _ProcessStuckError:
            time.sleep(_RETRY_TIMEOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode > 128:
                # terminated by signal, no retry needed
                raise
            time.sleep(_RETRY_TIMEOUT)


def clean(dir_name):
    _Util.cmdCall("/usr/bin/git", "-C", dir_name, "reset", "--hard")  # revert any modifications
    _Util.cmdCall("/usr/bin/git", "-C", dir_name, "clean", "-xfd")    # delete untracked files


_STUCK_TIMEOUT = 60     # unit: second
_RETRY_TIMEOUT = 1      # unit: second


class _ProcessStuckError(Exception):

    def __init__(self, cmd, timeout):
        self.timeout = timeout
        self.cmd = cmd

    def __str__(self):
        return "Command '%s' stucked for %d seconds." % (self.cmd, self.timeout)


class _Util:

    @staticmethod
    def getGitSpeedEnv():
        return {
            "GIT_HTTP_LOW_SPEED_LIMIT": "1024",
            "GIT_HTTP_LOW_SPEED_TIME": "60",
        }

    @staticmethod
    def rmDirContent(dirpath):
        for filename in os.listdir(dirpath):
            filepath = os.path.join(dirpath, filename)
            try:
                shutil.rmtree(filepath)
            except OSError:
                os.remove(filepath)

    @staticmethod
    def cmdCall(cmd, *kargs):
        # call command to execute backstage job
        #
        # scenario 1, process group receives SIGTERM, SIGINT and SIGHUP:
        #   * callee must auto-terminate, and cause no side-effect
        #   * caller must be terminated by signal, not by detecting child-process failure
        # scenario 2, caller receives SIGTERM, SIGINT, SIGHUP:
        #   * caller is terminated by signal, and NOT notify callee
        #   * callee must auto-terminate, and cause no side-effect, after caller is terminated
        # scenario 3, callee receives SIGTERM, SIGINT, SIGHUP:
        #   * caller detects child-process failure and do appopriate treatment

        ret = subprocess.run([cmd] + list(kargs),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellExecWithStuckCheck(cmdList, envDict):
        if hasattr(selectors, 'PollSelector'):
            pselector = selectors.PollSelector
        else:
            pselector = selectors.SelectSelector

        # run the process
        proc = subprocess.Popen(cmdList,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=envDict)

        # redirect proc.stdout/proc.stderr to stdout/stderr
        # make CalledProcessError contain stdout/stderr content
        # terminate the process and raise exception if they stuck
        sStdout = ""
        sStderr = ""
        bStuck = False
        with pselector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            selector.register(proc.stderr, selectors.EVENT_READ)
            while selector.get_map():
                res = selector.select(_STUCK_TIMEOUT)
                if res == []:
                    bStuck = True
                    sys.stderr.write("Process stuck for %d second(s), terminated.\n" % (_STUCK_TIMEOUT))
                    proc.terminate()
                    break
                for key, events in res:
                    data = key.fileobj.read()
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    if key.fileobj == proc.stdout:
                        sStdout += data
                        sys.stdout.write(data)
                    elif key.fileobj == proc.stderr:
                        sStderr += data
                        sys.stderr.write(data)
                    else:
                        assert False

        proc.communicate()

        if proc.returncode > 128:
            time.sleep(1.0)
        if bStuck:
            raise _ProcessStuckError(proc.args, _STUCK_TIMEOUT)
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, proc.args, sStdout, sStderr)
