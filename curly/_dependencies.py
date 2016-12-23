"""
Calculate dependency resolution order.

Given a bunch of things with IDs and a way to determine the IDs of
direct dependencies of a thing, return a possible evaluation order or
raise an exception if not possible.

    sort(things, key=func)

    ordered(things, key=func, depends=func)

OR

Interface based:
    ordered(items)
where each item must have `id` and `dependencies` properties.

OR

Dependency-to-graph AND depth-first-graph

"""
def ordered(items):
