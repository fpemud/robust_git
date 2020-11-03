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
import re
import time
import fcntl
import errno
import shutil
from passlib import hosts

__author__ = "fpemud@sina.com (Fpemud)"
__version__ = "0.0.1"


def clone(*args):
    while True:
        try:
            _Util.shellExecWithStuckCheck(["/usr/bin/git", "clone"] + args, _Util.getGitSpeedEnv())
            break
        except _ProcessStuckError:
            time.sleep(_RETRY_TIMEOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode > 128:
                raise                    # terminated by signal, no retry needed
            time.sleep(_RETRY_TIMEOUT)


def pull(*args):
    assert not any(x not in args for x in ["-r", "--rebase", "--no-rebase"])

    while True:
        try:
            FmUtil.shellExecWithStuckCheck(["/usr/bin/git", "pull", "--rebase"] + args, _Util.getGitSpeedEnv())
            break
        except FmUtil.ProcessStuckError:
            time.sleep(_RETRY_TIMEOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode > 128:
                raise                    # terminated by signal, no retry needed
            time.sleep(_RETRY_TIMEOUT)


def pull_or_clones(*args):
    # pull is the default action
    # clone if not exists
    # clone if url differs
    # clone if pull fails
    pass


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
            "GIT_HTTP_LOW_SPEED_TIME", "60",
        }

    @staticmethod
    def shellExecWithStuckCheck(cmdList, envDict):
        if hasattr(selectors, 'PollSelector'):
            pselector = selectors.PollSelector
        else:
            pselector = selectors.SelectSelector

        # run the process
        proc = subprocess.Popen(cmdList,
                                sstdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
            raise _ProcessStuckError(proc.args, timeout)
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, proc.args, sStdout, sStderr)
