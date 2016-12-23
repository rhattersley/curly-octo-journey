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


for name in ('!ImportValue', '!Ref'):
    yaml.add_constructor(name, _Unary.constructor)
    yaml.add_representer(_Unary, _Unary.representer)


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
            metadata, parameters = yaml.safe_load_all(f)
        path, _ = os.path.splitext(path)
        bits = []
        while path:
            head, tail = os.path.split(path)
            bits.append(tail)
            path = head
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
        docs = list(yaml.load_all(rendered))
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


def create_stack(stack_defn):
    metadata, cf_yaml = stack_defn.create_yaml()
    name = metadata.get('name', stack_defn.name)
    #print(name)
    body = yaml.dump(cf_yaml)
    #print(body)
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
    create_stack(stack_defns[0])


if __name__ == '__main__':
    create_env('dev-oo-sec')
