from amethyst.response import Response, Status

import importlib
import inspect
import pkgutil
import sys
import textwrap


class PydocResource():
    @staticmethod
    def classify(thing):
        if inspect.ismodule(thing):
            return "module"
        elif inspect.isclass(thing):
            return "class"
        elif (inspect.isfunction(thing) or inspect.ismethod(thing) or
              inspect.ismethoddescriptor(thing) or inspect.isroutine(thing)):
            return "function"
        else:
            return "other"

    def doc_class(self, cls, name=None):
        lines = []

        if name is None:
            name = []

        name = ".".join(name + [cls.__name__])

        lines.append(f"### {name}")
        if (clsdoc := getattr(cls, "__doc__")):
            lines.append(f"```\n{clsdoc}\n```\n")

        members = {}
        members = {"class": [], "function": [], "other": []}

        for name, member in inspect.getmembers(cls):
            if name.startswith("_"):
                continue

            if (classification := self.classify(member)) in {"class", "function", "other"}:
                members[classification].append((name, member))

        members["class"].sort()
        for _, scls in members["class"]:
            lines.append(self.doc_cls(scls, name))

        members["function"].sort()
        for name, func in members["function"]:
            lines.append(self.doc_func(func))

        members["other"].sort()
        for name, other in members["other"]:
            lines.append(self.doc_other(name, other))

        return "\n".join(lines)

    def doc_func(self, func):
        lines = []

        lines.append("```")
        try:
            lines.append(f"{func.__name__}{inspect.signature(func)}")
        except ValueError:
            lines.append(f"{func.__name__}(...)")

        if (funcdoc := getattr(func, "__doc__")):
            lines.append(f"\n{textwrap.indent(funcdoc, '  ')}\n```\n")
        else:
            lines.append("```\n")

        return "\n".join(lines)

    def doc_other(self, name, other):
        doc = getattr(other, "__doc__", "")
        if doc and doc != type(other).__doc__:
            doc = textwrap.indent(doc, "  ")
            doc += "\n```\n"
        else:
            doc = "```"

        return f"```\n{name} = {other!r}\n{doc}"

    def doc_mod(self, modname):
        lines = []

        try:
            module = importlib.import_module(modname)
        except ImportError:
            return None

        ispkg = (getattr(module, "__package__", "") == modname)

        lines.append("=> _ Back to module index")
        lines.append("=> _/search Go to module by name")
        if "." in modname:
            components = modname.split(".")
            for i in range(len(components) - 1, 0, -1):
                lines.append("=> " + ".".join(components[:i]))

        if ispkg:
            lines.append(f"# {modname} (package)")
        else:
            lines.append(f"# {modname}")

        if (moddoc := getattr(module, "__doc__")):
            lines.append(f"```\n{moddoc}\n```")
        else:
            lines.append("This module has no docstring.")

        members = {"module": [], "class": [], "function": [], "other": []}
        for name, member in inspect.getmembers(module):
            if name.startswith("_"):
                continue

            members[self.classify(member)].append((name, member))

        if members["class"]:
            members["class"].sort()
            lines.append("## Classes")
            for name, cls in members["class"]:
                lines.append(self.doc_class(cls))

        if members["function"]:
            members["function"].sort()
            lines.append("## Functions")
            for name, func in members["function"]:
                lines.append(f"### {name}")
                lines.append(self.doc_func(func))

        if members["other"]:
            lines.append("## Other members")
            members["other"].sort()
            for name, other in members["other"]:
                lines.append(self.doc_other(name, other))

        if members["module"]:
            members["module"].sort()
            lines.append("## Modules")
            for name, mod in members["module"]:
                lines.append(f"=> {mod.__name__} {name}")

        return "\n".join(lines)

    def index(self):
        lines = []

        lines.append("=> _/search Go to module by name")

        lines.append("# Built-in modules")
        names = [name for name in sys.builtin_module_names if name != "__main__"]
        for name in sorted(names):
            lines.append(f"=> {name}")

        lines.append("# Python modules")
        for dirname in sorted(sys.path):
            display = dirname
            if display.startswith("/nix/store/"):
                display = f"(nix store)/{display[44:]}"

            lines.append(f"## {display}")
            modpkgs = []
            for importer, name, ispkg in pkgutil.iter_modules([dirname]):
                if any((0xD800 <= ord(ch) <= 0xDFFF) for ch in name):
                    # Ignore modules that contain surrogate characters
                    # (pydoc does this)
                    continue

                if name == "setup":
                    # never import "setup.py"
                    continue

                modpkgs.append((name, ispkg))

            for name, ispkg in sorted(modpkgs):
                if ispkg:
                    lines.append(f"=> {name} {name} (package)")
                else:
                    lines.append(f"=> {name}")

        return "\n".join(lines)


    async def __call__(self, ctx):
        path = ctx.path
        if not path:
            return Response(Status.REDIRECT_PERMANENT, ctx.orig_path + "/")

        path = path.strip("/")
        if not path or path == "_":
            text = self.index()

        elif path == "_/search":
            if ctx.query:
                try:
                    importlib.import_module(ctx.query)
                    return Response(Status.REDIRECT_TEMPORARY, "../" + ctx.query)
                except ImportError:
                    return Response(Status.INPUT, f"Sorry, I don't know about {ctx.query}. Module name?")

            return Response(Status.INPUT, "Module name?")
        else:
            text = self.doc_mod(path)

        if text is not None:
            return Response(
                Status.SUCCESS, "text/gemini", text.encode()
            )

        return Response(Status.NOT_FOUND, "text/gemini")
