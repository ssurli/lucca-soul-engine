import re
env = {}
for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

from neo4j import GraphDatabase
uri = env["NEO4J_URI"]; user = env["NEO4J_USERNAME"]; pwd = env["NEO4J_PASSWORD"]
print("URI:", uri)
print("USER:", user)
print("PWD len:", len(pwd), "caratteri")
print()

for scheme in ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"]:
    test = re.sub(r"^[a-z+]+://", scheme + "://", uri)
    try:
        d = GraphDatabase.driver(test, auth=(user, pwd))
        d.verify_connectivity()
        with d.session() as s:
            s.run("RETURN 1").single()
        d.close()
        print("  OK   " + scheme + "   <-- FUNZIONA")
    except Exception as e:
        print("  FAIL " + scheme + "   " + type(e).__name__ + ": " + str(e)[:110])
