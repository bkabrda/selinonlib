#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ######################################################################
# Copyright (C) 2016-2017  Fridolin Pokorny, fridolin.pokorny@gmail.com
# This file is part of Selinon project.
# ######################################################################
"""Abstract representation of nodes in task/flow dependencies - a node is either a task or a flow"""

import os
import datetime
import abc
import re
from .globalConfig import GlobalConfig


class Node(metaclass=abc.ABCMeta):
    """
    An abstract class for node representation
    """
    def __init__(self, name):
        if not self.check_name(name):
            raise ValueError("Invalid node name '%s'" % name)
        self._name = name

    @abc.abstractstaticmethod
    def from_dict(dict_):
        """
        Construct node from a dict

        :return: instantiated node
        """
        pass

    @property
    def name(self):
        """
        :return: a name of the node
        """
        return self._name

    def _expand_queue_name(self, queue_name):
        """Assign queue name based on configuration, do expansion based on env variables if needed

        :param queue_name: name of queue as provided in config file or None
        :return: final name of the queue
        """
        queue_name = queue_name or GlobalConfig.default_dispatcher_queue
        try:
            return queue_name.format(**os.environ)
        except KeyError:
            if self.is_flow():
                err_msg = "Expansion of queue name based on environment variables failed for flow '%s', queue: '%s'" \
                          % (self.name, queue_name)
            else:
                err_msg = "Expansion of queue name based on environment variables failed for task '%s', queue: '%s' " \
                          % (self.name, queue_name)
            raise ValueError(err_msg)

    def is_flow(self):
        """
        :return: True if node represents a Flow
        """
        from .flow import Flow
        return isinstance(self, Flow)

    def is_task(self):
        """
        :return: True if node represents a Task
        """
        from .task import Task
        return isinstance(self, Task)

    @staticmethod
    def check_name(name):
        """
        Check whether name is a correct node (flow/task) name

        :param name: node name
        :return: True if name is a correct node name
        :rtype: bool
        """
        regexp = re.compile(r"^[_a-zA-Z][_a-zA-Z0-9]*$")
        return regexp.match(name)

    def parse_throttling(self, dict_):
        """
        Parse throttling from a dictionary

        :param dict_: dictionary from which throttling should be parsed
        :return: timedelta describing throttling countdown or None if not throttling applied
        :rtype: time.timedelta
        """
        if not dict_:
            return None

        if not isinstance(dict_, dict):
            raise ValueError("Definition of throttling expects key value definition, got %s instead in '%s'"
                             % (dict_['throttling'], self.name))
        try:
            return datetime.timedelta(**dict_)
        except TypeError:
            raise ValueError("Wrong throttling definition in '%s', expected values are %s"
                             % (self.name,
                                ['days', 'seconds', 'microseconds', 'milliseconds', 'minutes', 'hours', 'weeks']))
