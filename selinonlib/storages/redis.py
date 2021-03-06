#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ######################################################################
# Copyright (C) 2016-2017  Fridolin Pokorny, fridolin.pokorny@gmail.com
# This file is part of Selinon project.
# ######################################################################
"""
Selinon adapter for Redis database
"""

import json
try:
    import redis
except ImportError:
    raise ImportError("Please install redis using `pip3 install redis` in order to use RedisStorage")
from selinon import DataStorage


class RedisStorage(DataStorage):  # pylint: disable=too-many-instance-attributes
    """
    Selinon adapter for Redis database
    """
    def __init__(self, host="localhost", port=6379, db=0, password=None, socket_timeout=None, connection_pool=None,
                 charset='utf-8', errors='strict', unix_socket_path=None):
        super().__init__()
        self.conn = None
        self.host = host
        self.port = port
        self.db = db  # pylint: disable=invalid-name
        self.password = password
        self.socket_timeout = socket_timeout
        self.connection_pool = connection_pool
        self.charset = charset
        self.errors = errors
        self.unix_socket_path = unix_socket_path

    def is_connected(self):
        return self.conn is not None

    def connect(self):
        self.conn = redis.Redis(host=self.host, port=self.port, db=self.db, password=self.password,
                                socket_timeout=self.socket_timeout, connection_pool=self.connection_pool,
                                charset=self.charset, errors=self.errors)

    def disconnect(self):
        if self.is_connected():
            self.conn.connection_pool.disconnect()
            self.conn = None

    def retrieve(self, flow_name, task_name, task_id):
        assert self.is_connected()

        ret = self.conn.get(task_id)

        if ret is None:
            raise FileNotFoundError("Record not found in database")

        record = json.loads(ret.decode(self.charset))

        assert record.get('task_name') == task_name
        return record.get('result')

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert self.is_connected()

        record = {
            'node_args': node_args,
            'flow_name': flow_name,
            'task_name': task_name,
            'task_id': task_id,
            'result': result
        }

        self.conn.set(task_id, json.dumps(record))
        return task_id
