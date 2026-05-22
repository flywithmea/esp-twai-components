# ESP TWAI Components

This repository hosts reusable ESP-IDF components for TWAI (CAN) controller drivers and protocol stacks.

## Repository Layout

- `controller_drivers/`: TWAI controller implementations
- `protocol_stacks/`: higher-level CAN/TWAI protocol layers

## Build Documentation Locally

Install prerequisites:

- `mdbook`
- `mdbook-mermaid` (`cargo install mdbook-mermaid --locked`)
- `doxygen`
- `esp-doxybook` (`python3 -m pip install esp-doxybook`)

Build all component docs:

```bash
python3 tools/build_docs.py --output-dir docs_build_output
```

Output will be generated under `docs_build_output/`.
