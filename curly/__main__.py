#!/usr/bin/env python
"""
curly <path-to-env-dir>

"""
import os
import os.path

import boto3
import jinja2
import jinja2.meta
import yaml


class _Unary:
    def __init__(self, tag, arg):
        self.tag = tag
        self.arg = arg

    @staticmethod
    def constructor(loader, node):
        value = loader.construct_scalar(node)
        return _Unary(node.tag, value)

    @staticmethod
    def representer(dumper, data):
        return dumper.represent_scalar(data.tag, data.arg)


class CFLoader(yaml.loader.Loader):
    pass


class CFDumper(yaml.dumper.Dumper):
    pass


for name in ('!ImportValue', '!Ref'):
    yaml.add_constructor(name, _Unary.constructor, CFLoader)
    yaml.add_representer(_Unary, _Unary.representer, CFDumper)


class ConfigLoader(yaml.loader.Loader):
    pass


yaml.add_constructor('!Resource', _Unary.constructor, ConfigLoader)


class Template:
    def __init__(self, name, metadata, body):
        self.name = name
        self.metadata = metadata
        self.body = body

    @staticmethod
    def from_path(path):
        with open(path) as f:
            metadata, body = yaml.safe_load_all(f)
        return Template(path, metadata, body) 


class StackDefn:
    def __init__(self, name, metadata, parameters):
        self.name = name
        # NB. YAML containing Jinja2 markup is NOT valid YAML, so we
        # can't load the template as YAML yet.
        self.metadata = metadata
        self.parameters = parameters

    def __repr__(self):
        return '<StackDefn: {}>'.format(self.metadata['template_path'])

    @staticmethod
    def from_path(path):
        with open(path) as f:
            metadata, parameters = yaml.load_all(f, Loader=ConfigLoader)
        path, _ = os.path.splitext(path)
        bits = []
        while path:
            head, tail = os.path.split(path)
            bits.append(tail)
            path = head
            # Don't actually add the path - use just the last bit to
            # make life easier when determining cross-stack
            # dependencies.
            break
        name = '-'.join(reversed(bits))
        return StackDefn(name, metadata, parameters)

    def create_yaml(self):
        jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
        jinja_template = jinja_env.get_template(self.metadata['template_path'])
        with open(jinja_template.filename) as f:
            ast = jinja_env.parse(f.read())
        required_parameters = jinja2.meta.find_undeclared_variables(ast)
        missing_parameters = required_parameters.difference(self.parameters)
        if missing_parameters:
            print('Missing parameters:', missing_parameters)
            exit()
        rendered = jinja_template.render(self.parameters)
        docs = list(yaml.load_all(rendered, Loader=CFLoader))
        assert 0 < len(docs) <= 2
        metadata = None
        if len(docs) == 1:
            body = docs[0]
        else:
            metadata, body = docs
        if metadata is None:
            metadata = {}
        return metadata, body


def read_env(env_dir):
    """Return all the StackDefns for the given directory."""
    stack_defns = []
    for dir_entry in os.scandir(env_dir):
        if not dir_entry.is_file():
            continue
        if not dir_entry.name.endswith('.yaml'):
            continue
        stack_defns.append(StackDefn.from_path(dir_entry.path))
    return stack_defns


def build_dependencies(stack_defns):
    all_dependencies = {}
    for stack_defn in stack_defns:
        dependencies = set()
        for value in stack_defn.parameters.values():
            if isinstance(value, _Unary) and value.tag == '!Resource':
                stack_name, output_name = value.arg.split('.')
                dependencies.add(stack_name)
        all_dependencies[stack_defn.name] = dependencies
    all_names = {stack_defn.name for stack_defn in stack_defns}
    used = set()
    for dependencies in all_dependencies.values():
        used = used.union(dependencies)
    roots = all_names - used
    assert roots
    def _tree(name):
        return {n: _tree(n) for n in all_dependencies[name]}
    tree = {name: _tree(name) for name in roots}

    # Depth-first traversal of dependencies,
    # avoiding multiple traversal of shared dependencies.
    out = []
    def _down(node):
        for name, subnode in node.items():
            _down(subnode)
            if name not in out:
                out.append(name)
    _down(tree)
    return out


def create_stack(stack_defn):
    metadata, cf_yaml = stack_defn.create_yaml()
    name = metadata.get('name', stack_defn.name)
    #print(name)
    body = yaml.dump(cf_yaml, Dumper=CFDumper)
    print(body)
    if 0:
        print('Getting client...')
        client = boto3.client('cloudformation')
        print('Validating...')
        print(client.validate_template(TemplateBody=body))
        print('Creating...')
        #import botocore
        #try:
        response = client.create_stack(StackName=name, TemplateBody=body)
        #except botocore.exceptions.ClientError as e:
        # e.response['Error']['Code'] == 'AlreadyExistsException'
        print(response)


def create_env(env_dir):
    stack_defns = read_env(env_dir)
    dependencies = build_dependencies(stack_defns)
    print(dependencies)
    #create_stack(stack_defns[0])


if __name__ == '__main__':
    create_env('dev-oo-sec')
