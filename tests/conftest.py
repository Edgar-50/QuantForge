import os, tempfile
# isolate test runs from any developer database (must be set before app import)
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "qf_test.db")
