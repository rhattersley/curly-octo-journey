import os

import jinja2
import yaml


class _StackOutput:
    def __init__(self, stack, output):
        self.stack = stack
        self.output = output

    def __repr__(self):
        return '!Ref {}.{}'.format(self.stack, self.output)

    @staticmethod
    def constructor(loader, node):
        value = loader.construct_scalar(node)
        stack, output = value.split('.')
        return _StackOutput(stack, output)


yaml.add_constructor('!StackOutput', _StackOutput.constructor)


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


def _fiddle(stack_name, t):
    w = yaml.load(t)
    for name, detail in w.get('Outputs', {}).items():
        if 'Export' not in detail:
            detail['Export'] = {'Name': '{}-{}'.format(stack_name, name)}
    return yaml.dump(w, default_flow_style=False)


def go():
    dependencies = {}
    for path in os.listdir('config'):
        stack_name, _ = path.split('.')
        #print('Loading', path)
        with open('config/' + path) as f:
            config = yaml.load(f)
            import_keys = []
            for key, value in config.items():
                if isinstance(value, _StackOutput):
                    #print(stack_name, 'depends on', value.stack)
                    d = dependencies.setdefault(stack_name, [])
                    d.append(value.stack)
                    import_keys.append(key)
            #print('Import keys:', import_keys)
            for key in import_keys:
                ref = config[key]
                config[key] = '!ImportValue {}-{}'.format(ref.stack, ref.output)
            #print('New config:', config)
            p = 'templates/' + config['template'] + '.yaml'
            #print(p)
            with open(p) as tf:
                stuff = tf.read()
            #print('Raw:', stuff)
            jinja_template = jinja2.Template(stuff)
            template = jinja_template.render(config)
            template = _fiddle(stack_name, template)
            #print(template)
            with open('output/' + stack_name + '.yaml', 'w') as out:
                out.write(template)
                out.write('\n')
        #break
    #print(dependencies)


if __name__ == '__main__':
    go()
