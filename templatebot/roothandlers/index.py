__all__ = ('get_index',)

from aiohttp import web
from templatebot.routes import root_routes


@root_routes.get('/')
async def get_index(request):
    name = request.config_dict['api.lsst.codes/name']
    return web.Response(text=name)
