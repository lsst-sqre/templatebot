### Other changes

- Cap `fastapi` below 0.140. FastAPI 0.140.0 made `Dependant` a slotted dataclass, which breaks FastStream's FastAPI plugin because it sets extra attributes on `Dependant` instances (`AttributeError: 'Dependant' object has no attribute 'model' and no __dict__ for setting new attributes`). The upper bound keeps `make update` from baking a broken FastAPI into `uv.lock`. Remove the cap once [ag2ai/faststream#2959](https://github.com/ag2ai/faststream/issues/2959) is fixed.
