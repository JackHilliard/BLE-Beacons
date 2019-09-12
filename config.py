import json
import os

with opn(os.environ['CONFIG']) as json_data:
    conf = json.loads(json_data)
