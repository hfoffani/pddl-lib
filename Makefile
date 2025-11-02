
# ANTLR configuration
ANTLRVERSION=4.13.2
ANTLRJAR=antlr-$(ANTLRVERSION)-complete.jar
ANTLRURL=https://www.antlr.org/download/$(ANTLRJAR)
ANTLR=java -jar $(ANTLRJAR)
GRUN=java -cp $(ANTLRJAR) org.antlr.v4.gui.TestRig

ANTLRLANG=-Dlanguage=Python3
UV=uv
PYTHON=uv run python
PIP=uv pip

export CLASSPATH:=.:$(ANTLRJAR)

# Default target: test grammar and run Python tests
all: testgrammar test

# Download ANTLR JAR if not present
$(ANTLRJAR):
	@echo "Downloading ANTLR $(ANTLRVERSION)..."
	@curl -L -o $(ANTLRJAR) $(ANTLRURL)

# Initialize uv environment
init:
	@echo "Initializing uv environment..."
	$(UV) sync

# Test ANTLR grammar with Java
testgrammar: $(ANTLRJAR) pddl.g4
	@echo "Testing ANTLR grammar..."
	mkdir -p tmp && \
	$(ANTLR) -o tmp pddl.g4 && \
	cd tmp && javac *.java && \
	$(GRUN) pddl domain ../examples-pddl/domain-01.pddl && \
	$(GRUN) pddl problem ../examples-pddl/problem-01.pddl

# Generate Python parser from ANTLR grammar
pyparser: $(ANTLRJAR) pddl.g4
	@echo "Generating Python parser..."
	mkdir -p pddlpy && \
	$(ANTLR) $(ANTLRLANG) -o pddlpy pddl.g4

# Run Python tests
test: pyparser pddlpy/pddl.py
	@echo "Running Python tests..."
	$(PYTHON) -m pddlpy.test

# Build distribution with uv
build: test
	@echo "Building distribution..."
	$(UV) build

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/ build/ pddlpy.egg-info/ tmp/
	rm -f pddlpy/pddlLexer.py pddlpy/pddlParser.py pddlpy/pddlListener.py pddlpy/*.interp pddlpy/*.tokens
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Run demo
demo: test
	@echo "Running demos..."
	for i in 1 2 3 4 6; do $(PYTHON) demo.py $$i ; done

# Test published package from TestPyPI using Docker
testpublish:
	@echo "Testing pddlpy installation from TestPyPI..."
	@echo "Building Docker image..."
	docker build -f testpublish/Dockerfile -t pddlpy-testpypi .
	@echo ""
	@echo "Running tests in Docker container..."
	docker run --rm pddlpy-testpypi
	@echo ""
	@echo "✓ TestPyPI installation test completed"

# Publishing targets (kept for backwards compatibility)
pypitest: build
	@echo "Publishing to TestPyPI... (credentials in ~/.pypirc)"
	$(UV) run twine upload --repository testpypi --verbose dist/`ls -t dist | head -1`

pypipublish: build
	@echo "Publishing to PyPI... (credentials in ~/.pypirc)"
	$(UV) run twine upload --verbose dist/`ls -t dist | head -1`

# Help target
help:
	@echo "Available targets:"
	@echo "  all          - Run grammar tests and Python tests (default)"
	@echo "  init         - Initialize uv environment"
	@echo "  testgrammar  - Test ANTLR grammar with Java"
	@echo "  pyparser     - Generate Python parser from grammar"
	@echo "  test         - Run Python tests"
	@echo "  build        - Build distribution packages"
	@echo "  clean        - Remove build artifacts"
	@echo "  demo         - Run demo scripts"
	@echo "  testpublish  - Test package installation from TestPyPI (Docker)"
	@echo "  pypitest     - Publish to TestPyPI"
	@echo "  pypipublish  - Publish to PyPI"

.PHONY: all init testgrammar pyparser test build clean demo testpublish pypitest pypipublish help
