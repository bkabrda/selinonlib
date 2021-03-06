#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ######################################################################
# Copyright (C) 2016-2017  Fridolin Pokorny, fridolin.pokorny@gmail.com
# This file is part of Selinon project.
# ######################################################################
"""A queue that respect timestamps of records that were pushed into it"""

import heapq


class TimeQueue(object):
    """A queue that respect timestamps of records that were pushed into it"""
    class _TimeQueueItem(object):
        """TimeQueue internal item"""
        def __init__(self, time, record):
            """
            :param time: timestamp of record
            :param record: record that should be stored
            """
            self.time = time
            self.record = record

        def __lt__(self, other):
            return self.time < other.time

        def __repr__(self):
            return "%s(%s, %s)" % (self.__class__.__name__, self.time, self.record)

    def __init__(self):
        self._queue = []

    def push(self, time, record):
        """Push record with the given timestamp to queue

        :param time: time of the record
        :param record: record to be pushed
        """
        heapq.heappush(self._queue, self._TimeQueueItem(time, record))

    def pop(self):
        """Remove and return the top record in the queue

        :return: time and record tuple that were stored
        """
        result = heapq.heappop(self._queue)
        return result.time, result.record

    def top(self):
        """Return the top record in the queue, do not remove it from the queue

        :return: time and record tuple that were stored
        """
        result = self._queue[0]
        return result.time, result.record

    def is_empty(self):
        """
        :return: True if queue is empty
        """
        return len(self._queue) == 0

    def __repr__(self):
        return repr(self._queue)
