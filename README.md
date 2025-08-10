# Autocomplete Engine

A sophisticated autocomplete system that provides intelligent sentence completion suggestions based on text corpora. Built with Python, this system features efficient text processing, advanced scoring algorithms, and a clean modular architecture.

## Features

- **Multi-source Corpus Loading**: Load text files from multiple directories simultaneously
- **Intelligent Text Normalization**: Unicode-aware text processing with consistent matching
- **Advanced Scoring System**: Sophisticated ranking based on match quality and position
- **Modular Architecture**: Clean separation of concerns for maintainability
- **Command-line Interface**: Interactive testing and demonstration capabilities
- **Performance Optimized**: Designed for efficient processing of large text collections

## Project Structure

```
auto_complete/
├── src/
│   └── autocomplete/
│       ├── __init__.py          # Main module interface
│       ├── __main__.py          # Command-line interface
│       ├── engine.py            # Core engine and coordination
│       ├── config.py            # Configuration constants
│       ├── loader.py            # Corpus loading and text normalization
│       ├── models.py            # Data structures and models
│       ├── search.py            # Search algorithms and scoring
│       └── index.py             # N-gram index building (future)
├── data/                        # Sample data directory
└── README.md                    # This file
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd google-team4/auto_complete
```

2. Ensure you have Python 3.8+ installed:
```bash
python --version
```

3. The project uses only standard library modules, so no additional dependencies are required.

## Usage

### Command Line Interface

The easiest way to test the system is through the interactive command-line interface:

```bash
# Load corpus from one or more directories
python -m autocomplete /path/to/texts /another/path

# Example with sample data
python -m autocomplete data/sample
```

### Programmatic Usage

```python
from autocomplete import load_corpus, get_best_k_completions

# Load corpus from text files
corpus = load_corpus(['/path/to/books', '/path/to/articles'])

# Get completion suggestions
completions = get_best_k_completions("hello wo")

# Process results
for completion in completions:
    print(f"Score: {completion.score}")
    print(f"Text: {completion.completed_sentence}")
    print(f"Source: {completion.source_text}")
    print(f"Offset: {completion.offset}")
    print("---")
```

## Configuration

Key configuration options can be modified in `src/autocomplete/config.py`:

- `TOP_K`: Maximum number of completion suggestions (default: 5)
- `GRAM`: N-gram size for index building (default: 3)
- `BUILD_INDEX`: Enable/disable inverted index (default: False)
- `ENCODING`: Text file encoding (default: "utf-8")
- `GLOB_PATTERN`: File pattern for corpus loading (default: "*.txt")

## Text Processing

The system applies consistent text normalization to ensure reliable matching:

1. **Case Folding**: Convert to lowercase for case-insensitive matching
2. **Punctuation Removal**: Unicode-aware removal of punctuation and symbols
3. **Whitespace Normalization**: Collapse multiple spaces and trim edges
4. **Encoding Handling**: Graceful handling of various text encodings

## Scoring Algorithm

Completions are ranked using a sophisticated scoring system:

- **Base Score**: 2 × number of matched characters
- **Position Penalties**: Single edit penalties based on match position
- **Tie-breaking**: Alphabetical order of completed sentences

## Architecture

### Core Components

- **Engine**: Main interface and coordination layer
- **Loader**: Corpus loading and text normalization
- **Models**: Data structures for sentences, corpus, and results
- **Search**: Search algorithms and scoring (placeholder for future implementation)
- **Index**: N-gram inverted index for performance optimization (placeholder)

### Data Flow

1. **Loading**: Text files → Normalized sentences → Corpus object
2. **Search**: User prefix → Normalized query → Candidate matching → Scoring → Ranking
3. **Results**: Ranked completions with metadata (score, source, offset)

## Development Status

### Completed
- ✅ Corpus loading and text normalization
- ✅ Data models and structures
- ✅ Core engine architecture
- ✅ Command-line interface
- ✅ Configuration management

### In Progress
- 🔄 Search algorithm implementation
- 🔄 Scoring system implementation
- 🔄 Performance optimization

### Planned
- 📋 N-gram inverted index
- 📋 Advanced search algorithms
- 📋 Performance benchmarking
- 📋 Unit tests and integration tests

## Contributing

This project follows a modular architecture to facilitate collaborative development:

1. **Module A**: Corpus loading and text processing (completed)
2. **Module B**: Search algorithms and scoring (in progress)
3. **Module C**: Performance optimization and indexing (planned)

Each module has clear interfaces and can be developed independently.

## Testing

### Sample Data

The `data/sample/` directory contains sample text files for testing:

```bash
# Test with sample data
python -m autocomplete data/sample
```

### Interactive Testing

The command-line interface provides an interactive way to test completions:

```
> hello wo
85 | sample/a.txt:1234 | hello world, how are you today?
72 | sample/b.txt:567 | hello world program in python
```

## Performance Considerations

- **Memory Usage**: Corpus is loaded entirely into memory for fast access
- **Search Complexity**: Currently O(n) where n is the number of sentences
- **Future Optimization**: N-gram index will reduce search complexity to O(1) for candidate retrieval
- **Text Processing**: Efficient Unicode-aware normalization with minimal allocations

## Troubleshooting

### Common Issues

1. **No results returned**: Ensure corpus is loaded before calling `get_best_k_completions()`
2. **Encoding errors**: Check file encoding or modify `ENCODING` in config.py
3. **Empty search results**: Search module is currently a placeholder - implementation in progress

### Debug Mode

Enable verbose output by modifying the engine module or adding debug logging.

## License

This project is part of Google Team 4's coursework and follows academic integrity guidelines.

## Authors

- **Google Team 4**: Main development team
- **Module A**: Corpus loading and text processing
- **Module B**: Search algorithms and scoring
- **Module C**: Performance optimization

## Version History

- **v1.0.0**: Initial implementation with corpus loading and basic architecture
- **v1.1.0**: Search and scoring implementation (in progress)
- **v1.2.0**: Performance optimization and indexing (planned)

---

For questions or contributions, please refer to the project documentation or contact the development team.
