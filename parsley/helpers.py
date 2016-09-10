#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ####################################################################
# Copyright (C) 2016  Fridolin Pokorny, fpokorny@redhat.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# ####################################################################

import os
import re
import json
import abc
from contextlib import contextmanager


def dict2strkwargs(d):
    """
    Convert a dictionary into arguments to a string representation that can be used as arguments to a function
    """
    ret = ""
    for k, v in d.items():
        if len(ret) > 0:
            ret += ", "
        ret += "%s=%s" % (k, expr2str(v))
    return ret


def expr2str(e):
    """
    Convert a Python expression into a Python code
    """
    if isinstance(e, dict):
        return str(e)
    elif isinstance(e, list):
        # s/'['foo']['bar']'/['foo']['bar']/ (get rid of leading ')
        return "%s" % e
    elif isinstance(e, str):
        return "'%s'" % e
    else:
        # some build in type such as bool/int/...
        return "%s" % str(e)


def keylist2str(keylist):
    """
    Convert keylist to a string representation

    :param keylist: keylist to be converted
    :type keylist: list
    :return: string representation
    :rtype: str
    """
    return "".join(map(lambda x: "['" + str(x) + "']", keylist))


@contextmanager
def pushd(new_dir):
    """
    Traverse directory tree in push/pop manner

    :param new_dir: new directory to cd to
    :type new_dir: str
    """
    prev_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(prev_dir)


def dict2json(o, pretty=True):
    """
    Convert dict to json (string)

    :param o: dictionary to be converted
    :param pretty: if True, nice formatting will be used
    :type pretty: bool
    :return: formatted dict in json
    :rtype: str
    """
    if pretty is True:
        return json.dumps(o, sort_keys=True, separators=(',', ': '), indent = 2)
    else:
        return json.dumps(o)
