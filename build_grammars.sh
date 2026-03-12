#!/bin/bash
set -e

# 1. Create vendor directory if missing
mkdir -p vendor
cd vendor

# 2. Clone official grammars
# Python
if [ ! -d tree-sitter-python ]; then
  git clone https://github.com/tree-sitter/tree-sitter-python.git
fi
# SQL
if [ ! -d tree-sitter-sql ]; then
  git clone https://github.com/m-novikov/tree-sitter-sql.git
fi
# YAML
if [ ! -d tree-sitter-yaml ]; then
  git clone https://github.com/ikatyang/tree-sitter-yaml.git
fi

# 3. Generate parser/scanner for YAML (schema)
cd tree-sitter-yaml
if [ -f schema/update-schema.js ]; then
  node schema/update-schema.js core
fi
npx tree-sitter generate || true
cd ..

# 4. Build Python bindings for each grammar
for lang in tree-sitter-python tree-sitter-sql tree-sitter-yaml; do
  cd $lang
  if [ -f setup.py ]; then
    python3 setup.py build_ext --inplace || true
  fi
  cd ..
done

echo "All grammars cloned and built."
