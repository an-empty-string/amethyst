from amethyst.response import Response, Status


class RedirectResource:
    def __init__(self, to, permanent=False):
        self.to = to
        self.permanent = permanent

    async def __call__(self, ctx):
        new_path = f"/{ctx.path}".replace("//", "/")
        new_path = f"{self.to.rstrip('/')}{new_path}"

        if self.permanent:
            return Response(Status.REDIRECT_PERMANENT, new_path)
        else:
            return Response(Status.REDIRECT_TEMPORARY, new_path)
