def get_path_components(path):
    path = path.strip("/").split("/")
    path = [c for c in path if c]

    normalized = []
    for comp in path:
        if comp == ".":
            continue
        elif comp == "..":
            if normalized:
                normalized.pop()
            else:
                raise ValueError("URL tried to traverse above root")
        else:
            normalized.append(comp)

    return normalized
