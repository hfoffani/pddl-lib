# Dockerfile to test pddlpy installation from TestPyPI
FROM python:3.11-slim

# Set working directory
WORKDIR /test

# Install pip and upgrade it
RUN pip install --no-cache-dir --upgrade pip

# Install pddlpy from TestPyPI
# Note: TestPyPI may not have all dependencies, so we install antlr4-python3-runtime from PyPI first
RUN pip install --no-cache-dir antlr4-python3-runtime==4.13.2 && \
    pip install --no-cache-dir --index-url https://test.pypi.org/simple/ --no-deps pddlpy

# Copy test files from parent directories
COPY demo.py /test/
COPY examples-pddl/domain-03.pddl /test/examples-pddl/domain-03.pddl
COPY examples-pddl/problem-03.pddl /test/examples-pddl/problem-03.pddl

# Run the test (demo 3 uses domain-03 and problem-03)
CMD ["python", "demo.py", "3"]
