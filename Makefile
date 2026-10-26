PYTHON ?= venv/Scripts/python.exe

.PHONY: verify-hw06 test-hw06 verify-hw07

verify-hw06:
	$(PYTHON) verify_hw06.py

test-hw06:
	$(PYTHON) -m pytest tests -q

verify-hw07:
	$(PYTHON) verify_hw07.py
