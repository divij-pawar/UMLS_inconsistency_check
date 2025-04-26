# 🧠 UMLS Inconsistency Checker

This tool detects structural and semantic inconsistencies in the Unified Medical Language System (UMLS) ontology, specifically identifying:

1. **Parent-Child Loops** – cycles in hierarchical relationships (e.g., A is a child of B, B is a child of C, C is a child of A).
2. **Broader-Than Violations** – contradictory broader-than relationships (e.g., A is broader than B and B is also broader than A).

---

## 📦 Setup

### Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

**Dependencies include:**
- `networkx`
- `tqdm`

You can also install manually:

```bash
pip install networkx tqdm
```

---

## ▶️ How to Run

```bash
python umls_checker.py --input /path/to/MRREL.RRF --type [parent-child|broader-than|both]
```

### Arguments:
- `--input` (`-i`): Path to the UMLS `MRREL.RRF` file (required)
- `--type` (`-t`): Type of inconsistency to check:
  - `parent-child`: Detects loops in the hierarchical structure (e.g., `CHD`, `PAR` relationships)
  - `broader-than`: Detects semantic contradictions in broader-than (`RB`, `RN`) relationships
  - `both`: Runs both checks

---

## 📄 Input Format

Your input must be the UMLS `MRREL.RRF` file, which contains relationships between concept CUIs.

Key relationships used:
- `CHD`: Child-of (converted to Parent → Child)
- `PAR`: Parent-of
- `RB`: Broader-than
- `RN`: Narrower-than (inverted to align with `RB`)

Example line (simplified):
```
C0001|C0002|PAR|CHD|...
```

---

## 📊 Output

Results will be saved in the `./output/` directory and include:

| File | Description |
|------|-------------|
| `parent_child_cycles_*.csv` | List of all parent-child loops (one per row) |
| `broader_than_conflicts_*.csv` | List of broader-than semantic contradictions |
| `duplicates_*.csv` | Duplicate edges found in the relationships |
| `self_loops_*.csv` | Any self-referencing CUIs (e.g., C0001 → C0001) |
| `analysis_statistics_*.csv` | Summary of counts, timing, and performance metrics |

Each result includes source-target CUIs and the violation path for context.

---