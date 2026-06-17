.PHONY: gen sync-proto install test

# Regenerate the protobuf/gRPC bindings under quorum/v1 from proto/.
gen:
	buf lint
	buf generate

# Refresh the vendored protos from a local checkout of the quorum server repo,
# then regenerate. Override QUORUM_REPO to point at your checkout.
QUORUM_REPO ?= ../quorum
sync-proto:
	cp $(QUORUM_REPO)/proto/quorum/v1/auth.proto $(QUORUM_REPO)/proto/quorum/v1/chat.proto proto/quorum/v1/
	$(MAKE) gen

# Editable install into the active environment.
install:
	pip install -e .

test:
	python -m pytest -q
