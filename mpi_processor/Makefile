# Makefile for MPI Parallel Exam Evaluator
# Requires: OpenMPI, g++ compiler

# Compiler and flags
CXX = mpic++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
TARGET = evaluator
SOURCES = evaluator.cpp

# Default target
all: $(TARGET)

# Build the evaluator
$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCES)
	@echo "MPI Evaluator compiled successfully!"
	@echo "Usage: mpirun -n <num_processes> ./$(TARGET) <input_file> <output_file>"

# Clean build artifacts
clean:
	rm -f $(TARGET)
	@echo "Cleaned build artifacts"

# Test compilation without building
test:
	$(CXX) $(CXXFLAGS) -c $(SOURCES)
	@echo "Compilation test successful"
	rm -f *.o

# Install to parent directory (for backend integration)
install: $(TARGET)
	@echo "Installing to parent directory for backend integration..."
	@if [ ! -f $(TARGET) ]; then \
		echo "Error: $(TARGET) not found. Run 'make' first."; \
		exit 1; \
	fi
	@echo "$(TARGET) is ready at: $(shell pwd)/$(TARGET)"

# Show MPI information
info:
	@echo "=== MPI Environment Information ==="
	@which mpic++ || echo "mpic++ not found in PATH"
	@which mpirun || echo "mpirun not found in PATH"
	@mpic++ --version 2>/dev/null || echo "Cannot get mpic++ version"
	@echo ""
	@echo "To install OpenMPI on different systems:"
	@echo "  Ubuntu/Debian: sudo apt-get install openmpi-bin openmpi-dev"
	@echo "  CentOS/RHEL:   sudo yum install openmpi openmpi-devel"
	@echo "  macOS:         brew install open-mpi"
	@echo "  Windows:       Use Microsoft MPI or Intel MPI"

# Help
help:
	@echo "Available targets:"
	@echo "  all      - Build the evaluator (default)"
	@echo "  clean    - Remove build artifacts"
	@echo "  test     - Test compilation without building"
	@echo "  install  - Install evaluator for backend integration"
	@echo "  info     - Show MPI environment information"
	@echo "  help     - Show this help message"

.PHONY: all clean test install info help 