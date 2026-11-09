Check date: 2026-11-09.
Outcome 1: make install exits 0, followed by the named verifier and collection
command exiting 0 against committed source b53982af26527c5f292c4d8a3a66d39d5f482ab5.
Supported bootstrap interpreter: /opt/homebrew/bin/python3.13 (3.13.13).
Commands: make install PYTHON=/opt/homebrew/bin/python3.13; then
.venv/bin/python scripts/verify_local_suite.py --source . --output <fresh-directory> --python <absolute-.venv/bin/python> --require-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 --require-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753;
.venv/bin/python -m pytest tests/test_pytest_collection.py.
Stop rule: at most two provisioning attempts or 30 minutes. Stop at the first
unrepairable dependency/capability failure; do not modify pins or speculate on code.
Blocking/drainable: acceptance remains blocked until provisioning succeeds;
retain actual installation evidence and report the first broken step meanwhile.
The unrestricted suite is invoked only through the explicitly requested verifier.
