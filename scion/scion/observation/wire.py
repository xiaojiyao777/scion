"""Child-only fixed JSON transport; all emitted payloads remain tainted."""
import json
import os


def read_request():
    with open("/input/request.json", encoding="utf-8") as stream:
        return json.load(stream)


def emit(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    fd = int(os.environ["SCION_OBSERVATION_RESULT_FD"])
    while raw:
        raw = raw[os.write(fd, raw):]
