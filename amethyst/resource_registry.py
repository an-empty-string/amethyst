from importlib.metadata import entry_points

registry = {}

for ep in entry_points().get("amethyst.resources"):
    registry[ep.name] = ep.load()