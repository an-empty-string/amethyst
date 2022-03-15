from importlib.metadata import entry_points

registry = {}

eps = entry_points().get("amethyst.resources")
if eps is not None:
    for ep in eps:
        registry[ep.name] = ep.load()
