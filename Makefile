.PHONY: test demo clean-demo venv

ROOT := $(CURDIR)
PYTHON ?= $(ROOT)/ve_reviewerloop/bin/python
REVIEWERLOOP ?= $(ROOT)/ve_reviewerloop/bin/reviewerloop
DEMO_DIR ?= /tmp/reviewerloop-demo

test:
	$(PYTHON) -m pytest -q

venv:
	python3 -m venv ve_reviewerloop
	ve_reviewerloop/bin/python -m pip install -e '.[dev]'

demo:
	$(PYTHON) examples/make_demo_project.py $(DEMO_DIR)
	$(REVIEWERLOOP) run \
		--project $(DEMO_DIR) \
		--config $(ROOT)/examples/demo_instructions.md \
		--reviewer "$(PYTHON) $(ROOT)/examples/demo_reviewer.py" \
		--writer "$(PYTHON) $(ROOT)/examples/demo_writer.py" \
		--test-cmd "$(PYTHON) -m pytest -q" \
		--max-cycles 2
	cd $(DEMO_DIR) && $(PYTHON) -m pytest -q
	@test -f $(DEMO_DIR)/.reviewerloop/issues/closed/RL-0001-addition.md
	@test ! -f $(DEMO_DIR)/.reviewerloop/issues/open/RL-0001-addition.md
	@echo "demo passed: $(DEMO_DIR)"

clean-demo:
	rm -rf $(DEMO_DIR)
