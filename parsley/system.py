#!/usr/bin/env python
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

import codegen
import graphviz
import os
import yaml
from .task import Task
from .storage import Storage
from .flow import Flow
from .edge import Edge
from .version import parsley_version
from .config import Config
from .logger import Logger
from .helpers import dict2strkwargs, expr2str
from .failures import Failures
from .taskClass import TaskClass


_logger = Logger.get_logger(__name__)


class System(object):
    """
    The representation of the whole system
    """
    def __init__(self, tasks=None, flows=None, storages=None, task_classes=None):
        self._flows = flows if flows else []
        self._tasks = tasks if tasks else []
        self._storages = storages if storages else []
        self._task_classes = task_classes if task_classes else []

    @property
    def tasks(self):
        """
        :return: tasks available in the system
        :rtype: List[Task]
        """
        return self._tasks

    @property
    def flows(self):
        """
        :return: flows available in the system
        :rtype: List[Flow]
        """
        return self._flows

    def _check_name_collision(self, name):
        """
        Tasks and Flows share name space, check for collisions
        :param name: a node name
        :raises: ValueError
        """
        if any(flow.name == name for flow in self._flows):
            raise ValueError("Unable to add node with name '%s', a flow with the same name already exist" % name)
        if any(task.name == name for task in self._tasks):
            raise ValueError("Unable to add node with name '%s', a task with the same name already exist" % name)

    def add_task(self, task):
        """
        Register a task in the system
        :param task: a task to be registered
        :type task: Task
        """
        self._check_name_collision(task.name)
        self._tasks.append(task)

    def add_flow(self, flow):
        """
        Register a flow in the system
        :param flow: a flow to be registered
        :type flow: flow
        """
        self._check_name_collision(flow.name)
        self._flows.append(flow)

    def add_storage(self, storage):
        # We need to check for name collision with tasks as well since we import them by name
        for task in self._tasks:
            if task.name == storage.name:
                raise ValueError("Storage has same name as task '%s'" % storage.name)

        for stored_storage in self._storages:
            if stored_storage.name == storage:
                raise ValueError("Multiple storages of the same name '{}'".format(storage.name))
        self._storages.append(storage)

    def storage_by_name(self, name, graceful=False):
        for storage in self._storages:
            if storage.name == name:
                return storage
        if not graceful:
            raise KeyError("Storage with name {} not found in the system".format(name))
        return None

    def task_by_name(self, name, graceful=False):
        """
        Find a task by its name
        :param name: a task name
        :param graceful: if True, no exception is raised if task couldn't be found
        :return: task with name 'name'
        :rtype: Task
        :raises: KeyError
        """
        for task in self._tasks:
            if task.name == name:
                return task
        if not graceful:
            raise KeyError("Task with name {} not found in the system".format(name))
        return None

    def flow_by_name(self, name, graceful=False):
        """
        Find a flow by its name
        :param name: a flow name
        :param graceful: if True, no exception is raised if flow couldn't be found
        :return: flow with name 'name'
        :rtype: Flow
        :raises: KeyError
        """
        for flow in self._flows:
            if flow.name == name:
                return flow
        if not graceful:
            raise KeyError("Flow with name '{}' not found in the system".format(name))
        return None

    def node_by_name(self, name, graceful=False):
        """
        Find a node (flow or task) by its name
        :param name: a node name
        :param graceful: if True, no exception is raised if node couldn't be found
        :return: flow with name 'name'
        :rtype: Node
        :raises: KeyError
        """
        node = self.task_by_name(name, graceful=True)

        if not node:
            node = self.flow_by_name(name, graceful=True)

        if not node and not graceful:
            raise KeyError("Entity with name '{}' not found in the system".format(name))

        return node

    def class_of_task(self, task):
        """
        Return task class of a task
        :param task: task to look task class for
        :return: TaskClass or None if a task class for task is not available
        """
        for task_class in self._task_classes:
            if task_class.task_of_class(task):
                return task_class
        return None

    def _dump_imports(self, output):
        """
        Dump used imports of tasks to a stream
        :param output: a stream to write to
        """
        predicates = set([])
        for flow in self._flows:
            for edge in flow.edges:
                predicates.update([p.__name__ for p in edge.predicate.predicates_used()])
        output.write('from parsley.predicates import %s\n' % ", ".join(predicates))

        output.write("\n# Tasks\n")

        for task in self._tasks:
            output.write("from {} import {}\n".format(task.import_path, task.class_name))

        output.write("\n# Storages\n")

        for storage in self._storages:
            if len(storage.tasks) > 0:
                output.write("from {} import {}\n".format(storage.import_path, storage.class_name))

        output.write('\n\n')

    def _dump_is_flow(self, output):
        """
        Dump is_flow() check to a stream
        :param output: a stream to write to
        """
        output.write('def is_flow(name):\n')
        output.write('    return name in %s\n\n' % str([flow.name for flow in self._flows]))

    def _dump_output_schemas(self, output):
        """
        Dump output schema mapping to a stream
        :param output: a stream to write to
        """
        output.write('output_schemas = {')
        printed = False
        for task in self._tasks:
            if task.output_schema:
                if printed:
                    output.write(",")
                output.write("\n    '%s': '%s'" % (task.name, task.output_schema))
                printed = True
        output.write('\n}\n\n')

    def _dump_get_task_instance(self, output):
        """
        Dump get_task_instance() function to a stream
        :param output: a stream to write to
        """
        output.write('def get_task_instance(name):\n')
        for task in self._tasks:
            output.write("    if name == '{}':\n".format(task.name))
            output.write("        return {}()\n\n".format(task.class_name))
        output.write("    raise ValueError(\"Unknown task with name '%s'\" % name)\n\n")

    def _dump_storage2instance_mapping(self, output):
        """
        Dump storage name to instance mapping to a stream
        :param output: a stream to write to
        """
        storage_var_names = []
        for storage in self._storages:
            if len(storage.tasks) > 0:
                storage_var_name = "_storage_%s" % storage.name
                output.write("%s = %s" % (storage_var_name, storage.class_name))
                if storage.configuration and isinstance(storage.configuration, dict):
                    output.write("(%s)\n" % dict2strkwargs(storage.configuration))
                elif storage.configuration:
                    output.write("(%s)\n" % expr2str(storage.configuration))
                else:
                    output.write("()\n")

                storage_var_names.append((storage.name, storage_var_name,))

        output.write('storage2instance_mapping = {\n')
        printed = False
        for storage_var_name in storage_var_names:
                if printed:
                    output.write(",\n")
                output.write("    '%s': %s" % (storage_var_name[0], storage_var_name[1]))
                printed = True

        output.write("\n}\n\n")

    def _dump_task2storage_mapping(self, output):
        """
        Dump task name to storage name mapping to a stream
        :param output: a stream to write to
        """
        output.write('task2storage_mapping = {\n')
        printed = False
        for storage in self._storages:
            for task in storage.tasks:
                if printed:
                    output.write(",\n")
                output.write("    '%s': '%s'" % (task.name, storage.name))
                printed = True
        output.write("\n}\n\n")

    @staticmethod
    def _dump_condition_name(flow_name, idx):
        """
        Create condition name for a dump
        :param flow_name: flow name
        :type flow_name: str
        :param idx: index of condition within the flow
        :type idx: int
        :return: condition function representation
        """
        assert(idx >= 0)
        return '_condition_{}_{}'.format(flow_name, idx)

    def _dump_condition_functions(self, output):
        """
        Dump condition functions to a stream
        :param output: a stream to write to
        """
        for flow in self._flows:
            for idx, edge in enumerate(flow.edges):
                output.write('def {}(db):\n'.format(self._dump_condition_name(flow.name, idx)))
                output.write('    return {}\n\n\n'.format(codegen.to_source(edge.predicate.ast())))

    def _dump_init_max_retry(self, output):
        """
        Dump max_retry initialization to a stream
        :param output: a stream to write to
        """
        output.write('def init_max_retry():\n')
        for task_class in self._task_classes:
            output.write('    %s.max_retry = %s\n' % (task_class.class_name, task_class.tasks[0].max_retry))
        output.write('\n')

    def _dump_init_time_limit(self, output):
        """
        Dump time limit initialization to a stream
        :param output: a stream to write to
        """
        output.write('def init_time_limit():\n')
        for task_class in self._task_classes:
            output.write('    %s.time_limit = %s\n' % (task_class.class_name, task_class.tasks[0].time_limit))
        output.write('\n')

    def _dump_init_output_schemas(self, output):
        """
        Dump init_output_schemas() to output stream
        :param output: a stream to write to
        """
        output.write('def init_output_schemas():\n')
        # we could make it not Celery specific by having map of output schemas
        for task_class in self._task_classes:
            if task_class.tasks[0].output_schema:
                output.write('    %s.output_schema_path = "%s"\n'
                             % (task_class.class_name, task_class.tasks[0].output_schema))
            else:
                output.write('    %s.output_schema_path = None\n' % task_class.class_name)
            output.write('    %s.output_schema = None\n' % task_class.class_name)
        output.write('\n')

    @staticmethod
    def _dump_init(output):
        """
        Dump init function to a stream
        :param output: a stream to write to
        :return:
        """
        output.write('def init():\n')
        output.write('    init_max_retry()\n')
        output.write('    init_time_limit()\n')
        output.write('    init_output_schemas()\n')
        output.write('\n')

    def _dump_edge_table(self, output):
        """
        Dump edge definition table to a stream
        :param output: a stream to write to
        """
        output.write('edge_table = {\n')
        for idx, flow in enumerate(self._flows):
            output.write("    '{}': [".format(flow.name))
            for idx_edge, edge in enumerate(flow.edges):
                if idx_edge > 0:
                    output.write(',\n')
                    output.write(' '*(len(flow.name) + 4 + 5)) # align to previous line
                output.write("{'from': %s" % str([node.name for node in edge.nodes_from]))
                output.write(", 'to': %s" % str([node.name for node in edge.nodes_to]))
                output.write(", 'condition': %s}" % self._dump_condition_name(flow.name, idx_edge))
            if idx + 1 < len(self._flows):
                output.write('],\n')
            else:
                output.write(']\n')
        output.write('}\n\n')

    def dump2stream(self, f):
        """
        Perform system dump to a Python source code to an output stream
        :param f: an output stream to write to
        """
        f.write('#!/usr/bin/env python\n')
        f.write('# auto-generated using Parsley v{}\n\n'.format(parsley_version))
        self._dump_imports(f)
        self._dump_get_task_instance(f)
        f.write('#'*80+'\n\n')
        self._dump_task2storage_mapping(f)
        self._dump_storage2instance_mapping(f)
        f.write('#'*80+'\n\n')
        self._dump_is_flow(f)
        f.write('#'*80+'\n\n')
        self._dump_output_schemas(f)
        f.write('#'*80+'\n\n')
        self._dump_init_max_retry(f)
        f.write('#'*80+'\n\n')
        self._dump_init_time_limit(f)
        f.write('#'*80+'\n\n')

        for flow in self._flows:
            if flow.failures:
                flow.failures.dump2stream(f, flow.name)

        f.write('failures = {')
        printed = False
        for i, flow in enumerate(self._flows):
            if flow.failures:
                if printed:
                    f.write(",")
                printed = True
                f.write("\n    '%s': %s" % (flow.name, flow.failures.starting_nodes_name(flow.name)))
        f.write('\n}\n\n')

        f.write('#'*80+'\n\n')
        self._dump_init_output_schemas(f)
        f.write('#'*80+'\n\n')
        self._dump_init(f)
        f.write('#'*80+'\n\n')
        self._dump_condition_functions(f)
        f.write('#'*80+'\n\n')
        self._dump_edge_table(f)
        f.write('#'*80+'\n\n')

    def dump2file(self, output_file):
        """
        Perform system dump to a Python source code
        :param output_file: an output file to write to
        """
        _logger.debug("Performing system dump to '%s'" % output_file)
        with open(output_file, 'w') as f:
            self.dump2stream(f)

    def plot_graph(self, output_dir, image_format=None):
        """
        Plot system flows to graphs - each flow in a separate file
        :param output_dir: output directory to write graphs of flows to
        :param image_format: image format, the default is svg if None
        :return: list of file names to which the graph was rendered
        :rtype: List[str]
        """
        _logger.debug("Rendering system flows to '%s'" % output_dir)
        ret = []
        image_format = image_format if image_format else 'svg'

        for flow in self._flows:
            storage_connections = []
            graph = graphviz.Digraph(format=image_format)
            graph.graph_attr.update(Config().style_graph())
            graph.node_attr.update(Config().style_task())
            graph.edge_attr.update(Config().style_edge())

            for idx, edge in enumerate(flow.edges):
                condition_node = "%s_%s" % (flow.name, idx)
                graph.node(name=condition_node, label=str(edge.predicate), _attributes=Config().style_condition())

                for node in edge.nodes_to:
                    # Plot storage connection
                    if node.is_flow():
                        graph.node(name=node.name, _attributes=Config().style_flow())
                    else:
                        graph.node(name=node.name)
                        if node.storage:
                            graph.node(name=node.storage.name, _attributes=Config().style_storage())
                            if (node.name, node.storage.name) not in storage_connections:
                                graph.edge(node.name, node.storage.name, _attributes=Config().style_store_edge())
                                storage_connections.append((node.name, node.storage.name,))
                    graph.edge(condition_node, node.name)
                for node in edge.nodes_from:
                    if node.is_flow():
                        graph.node(name=node.name, _attributes=Config().style_flow())
                    else:
                        graph.node(name=node.name)
                        if node.storage:
                            graph.node(name=node.storage.name, _attributes=Config().style_storage())
                            if (node.name, node.storage.name) not in storage_connections:
                                graph.edge(node.name, node.storage.name, _attributes=Config().style_store_edge())
                                storage_connections.append((node.name, node.storage.name,))
                    graph.edge(node.name, condition_node)

            # Plot failures as well
            if flow.failures:
                for failure in flow.failures.raw_definition:
                    if len(failure['nodes']) == 1 and \
                            (isinstance(failure['fallback'], bool) or len(failure['fallback']) == 1):
                        graph.node(name=failure['nodes'][0])

                        if isinstance(failure['fallback'], list):
                            fallback_node_name = failure['fallback'][0]
                        else:
                            fallback_node_name = str(failure['fallback'])

                        graph.node(name=fallback_node_name)
                        graph.edge(failure['nodes'][0], fallback_node_name,
                                   _attributes=Config().style_fallback_edge())
                    else:
                        graph.node(name=str(id(failure)), _attributes=Config().style_fallback_node())

                        for node_name in failure['nodes']:
                            if self.node_by_name(node_name).is_flow():
                                graph.node(name=node_name, _attributes=Config().style_flow())
                            else:
                                graph.node(name=node_name)
                            graph.edge(node_name, str(id(failure)), _attributes=Config().style_fallback_edge())

                        if failure['fallback'] is True:
                            graph.node(name=str(id(failure['fallback'])), label="True",
                                       _attributes=Config().style_fallback_true())
                            graph.edge(str(id(failure)), str(id(failure['fallback'])),
                                       _attributes=Config().style_fallback_edge())
                        else:
                            for node_name in failure['fallback']:
                                if self.node_by_name(node_name).is_flow():
                                    graph.node(name=node_name, _attributes=Config().style_flow())
                                else:
                                    graph.node(name=node_name)
                                graph.edge(str(id(failure)), node_name, _attributes=Config().style_fallback_edge())

            file = os.path.join(output_dir, "%s" % flow.name)
            graph.render(filename=file, cleanup=True)
            ret.append(file)
            _logger.info("Graph rendered to '%s.%s'" % (file, image_format))

        return ret

    def _post_parse_check(self):
        """
        Called once parse was done to ensure that system was correctly defined in config file
        :raises: ValueError
        """
        _logger.debug("Post parse check is going to be executed")
        # we want to have circular dependencies, so we need to check consistency after parsing since all flows
        # are listed (by names) in a separate definition
        for flow in self._flows:
            if len(flow.edges) == 0:
                raise ValueError("Empty flow: %s" % flow.name)

    def _check(self):
        """
        Check system for consistency
        :raises: ValueError
        """
        _logger.info("Checking system for consistency")

        for task_class in self._task_classes:
            task_ref = task_class.tasks[0]
            for task in task_class.tasks[1:]:
                if task_ref.output_schema != task.output_schema:
                    raise ValueError("Unable to set different output schemas to a same task class: %s and %s "
                                     "for class '%s', schemas: '%s' and '%s' might differ"
                                     % (task_ref.name, task.name, task_class.class_name,
                                        task_ref.output_schema, task.output_schema))

                if task.max_retry != task_ref.max_retry:
                    raise ValueError("Unable to set different max_retry to a same task class: %s and %s for class '%s'"
                                     % ((task.name, task.max_retry), (task_ref.name, task_ref.max_retry),
                                        task_class.class_name))

                if task.time_limit != task_ref.time_limit:
                    raise ValueError("Unable to set different time_limit to a same task class: %s and %s for class '%s'"
                                     % ((task.name, task.max_retry), (task_ref.name, task_ref.max_retry),
                                        task_class.class_name))

        for storage in self._storages:
            if len(storage.tasks) == 0:
                _logger.warning("Storage '{}' not used in any flow".format(storage.name))

        # We want to check that if we depend on a node, that node is being started at least once in the flow
        # This also covers check for starting node definition
        for flow in self._flows:
            try:
                all_nodes_from = set()
                all_nodes_to = set()

                starting_nodes_count = 0

                for edge in flow.edges:
                    if len(edge.nodes_from) == 0:
                        starting_nodes_count += 1

                    node_seen = {}
                    for node_from in edge.nodes_from:
                        if not node_seen.get(node_from.name, False):
                            node_seen[node_from.name] = True
                        else:
                            raise ValueError("Nodes cannot be dependent on a node of a same type mode than once; "
                                             "node from '%s' more than once in flow '%s'" % (node_from.name, flow.name))

                    edge.predicate.check()

                if starting_nodes_count > 1:
                    _logger.warning("Multiple starting nodes defined in flow '%s'" % flow.name)

                if starting_nodes_count == 0:
                    raise ValueError("No starting node found in flow '%s'" % flow.name)

                for edge in flow.edges:
                    all_nodes_from = all_nodes_from | set(edge.nodes_from)
                    all_nodes_to = all_nodes_to | set(edge.nodes_to)

                if flow.failures:
                    waiting_nodes_names = flow.failures.waiting_nodes_names()
                    waiting_nodes = []

                    for node_name in waiting_nodes_names:
                        node = self.node_by_name(node_name, graceful=True)
                        if not node:
                            raise KeyError("No such node with name '%s' in failure, flow '%s'" % (node_name, flow.name))
                        waiting_nodes.append(node)

                    started_nodes_names = flow.failures.started_nodes_names()
                    started_nodes = []

                    for node_name in started_nodes_names:
                        node = self.node_by_name(node_name, graceful=True)
                        if not node:
                            raise KeyError("No such node with name '%s' in failure fallback, flow '%s'"
                                           % (node_name, flow.name))
                        started_nodes.append(node)

                    all_nodes_from = all_nodes_from | set(waiting_nodes)
                    all_nodes_to = all_nodes_to | set(started_nodes)

                not_started = all_nodes_from - all_nodes_to

                error = False
                for node in not_started:
                    if node.is_task():
                        _logger.error("Dependency in flow '%s' on node '%s', but this node is not started in the flow"
                                      % (flow.name, node.name))
                        error = True

                if error:
                    raise ValueError("Dependency on not started node detected in flow '%s'" % flow.name)
            except:
                _logger.error("Check of flow '%s' failed" % flow.name)
                raise

    @staticmethod
    def from_files(nodes_definition_file, flow_definition_files, no_check=False):
        """
        Construct System from files
        :param nodes_definition_file: path to nodes definition file
        :param flow_definition_files: path to files that describe flows
        :param no_check: True if system shouldn't be checked for consistency (recommended to check)
        :return: System instance
        :rtype: System
        """
        system = System()

        with open(nodes_definition_file, 'r') as f:
            _logger.debug("Parsing '{}'".format(nodes_definition_file))
            try:
                content = yaml.load(f)
            except:
                _logger.error("Bad YAML file, unable to load tasks from {}".format(nodes_definition_file))
                raise

        for storage_dict in content.get('storages', []):
            storage = Storage.from_dict(storage_dict)
            system.add_storage(storage)

        for task_dict in content['tasks']:
            task = Task.from_dict(task_dict, system)
            task_class = system.class_of_task(task)
            if not task_class:
                task_class = TaskClass(task.class_name, task.import_path)
                system._task_classes.append(task_class)
            task_class.add_task(task)
            task.task_class = task_class
            system.add_task(task)

        for flow_name in content['flows']:
            flow = Flow(flow_name)
            system.add_flow(flow)

        if not isinstance(flow_definition_files, list):
            flow_definition_files = [flow_definition_files]

        for flow_file in flow_definition_files:
            with open(flow_file, 'r') as f:
                _logger.debug("Parsing '{}'".format(flow_file))
                try:
                    content = yaml.load(f)
                except:
                    _logger.error("Bad YAML file, unable to load flow from {}".format(flow_file))
                    raise

            for flow_def in content['flow-definitions']:
                flow = system.flow_by_name(flow_def['name'])

                if len(flow.edges) > 0:
                    raise ValueError("Multiple definitions of flow '%s'" % flow.name)

                for edge_def in flow_def['edges']:
                    edge = Edge.from_dict(edge_def, system, flow)
                    flow.add_edge(edge)

                if 'failures' in flow_def:
                    failures = Failures.construct(flow, flow_def['failures'])
                    flow.failures = failures

        system._post_parse_check()
        if not no_check:
            system._check()

        return system
