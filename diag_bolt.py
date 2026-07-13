import logging, sys, traceback
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logging.getLogger("neo4j").setLevel(logging.DEBUG)

env = {}
for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

import neo4j
from neo4j import GraphDatabase
print("DRIVER VERSION:", neo4j.__version__)

host = env["NEO4J_URI"].split("//")[1]
uri = "bolt+s://" + host          # connessione DIRETTA, niente routing
print("TEST URI:", uri)

try:
    d = GraphDatabase.driver(uri, auth=(env["NEO4J_USERNAME"], env["NEO4J_PASSWORD"]))
    with d.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
        print("RISULTATO:", s.run("RETURN 1 AS n").single()["n"])
    d.close()
    print(">>> FUNZIONA con bolt+s")
except Exception as e:
    print(">>> FALLITO:", type(e).__name__, e)
    print("--- causa interna ---")
    traceback.print_exc()
    cause = e.__cause__
    while cause:
        print("CAUSA:", type(cause).__name__, cause)
        cause = cause.__cause__
