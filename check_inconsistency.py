import argparse
import logging
import csv
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import networkx as nx
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ontology_checker.log")
    ]
)
log = logging.getLogger("UMLS-Checker")


# Extract relationships from MRREL.RRF
def load_relationships(filepath):
    child_relations = set()
    broader_relations = set()
    repeats = Counter()
    reflexives = set()
    rel_kinds = set()

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find file: {filepath}")

    with open(filepath, encoding="utf-8") as file:
        total_lines = sum(1 for _ in open(filepath, encoding="utf-8"))
        for line in tqdm(file, total=total_lines, desc="Reading MRREL.RRF"):
            fields = line.strip().split("|")
            if len(fields) < 5:
                continue

            src_cui, rel_type, tgt_cui = fields[0], fields[3], fields[4]
            rel_kinds.add(rel_type)

            if src_cui == tgt_cui:
                reflexives.add((src_cui, rel_type))
                continue

            edge = (src_cui, tgt_cui)

            if rel_type == "CHD":  # CHD = child, edge from parent -> child
                edge = (tgt_cui, src_cui)
                child_relations.add(edge)
                repeats[edge] += 1
            elif rel_type == "PAR":
                child_relations.add(edge)
                repeats[edge] += 1
            elif rel_type == "RB":  # RB = broader-than
                broader_relations.add(edge)
                repeats[edge] += 1
            elif rel_type == "RN":  # RN = narrower-than → reverse
                edge = (tgt_cui, src_cui)
                broader_relations.add(edge)
                repeats[edge] += 1

    return child_relations, broader_relations, repeats, reflexives, rel_kinds


# Depth-first cycle detection
def find_hierarchy_cycles(adjacency_list):
    visited = set()
    stack = set()
    found_cycles = []
    seen_signatures = set()

    def dfs(current, trail):
        if current in stack:
            idx = trail.index(current)
            loop = trail[idx:]
            key = tuple(sorted(loop))
            if key not in seen_signatures:
                seen_signatures.add(key)
                found_cycles.append(loop)
            return

        if current in visited:
            return

        visited.add(current)
        stack.add(current)
        trail.append(current)

        for neighbor in adjacency_list[current]:
            dfs(neighbor, trail)

        trail.pop()
        stack.remove(current)

    for node in list(adjacency_list):
        if node not in visited:
            dfs(node, [])

    return found_cycles


# Check broader-than contradictions
def identify_broader_issues(graph):
    problematic_pairs = []
    descendants_map = {n: set(nx.descendants(graph, n)) for n in graph.nodes}

    for source in graph:
        for target in descendants_map[source]:
            if source in descendants_map.get(target, set()):
                fwd_path = nx.shortest_path(graph, source, target)
                back_path = nx.shortest_path(graph, target, source)
                problematic_pairs.append({
                    "from": source,
                    "to": target,
                    "path": fwd_path + back_path[1:]
                })

    return problematic_pairs


# Save reports
def write_reports(cycles, contradictions, repeated, reflexive_links, stats, out_dir="./output"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    def write_csv(file_name, headers, rows):
        with open(Path(out_dir) / f"{file_name}_{timestamp}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    if cycles:
        write_csv("parent_child_cycles", ["ID", "Cycle"], [[i+1, " -> ".join(c)] for i, c in enumerate(cycles)])

    if contradictions:
        write_csv("broader_than_conflicts", ["ID", "Source", "Target", "Path"],
                  [[i+1, d["from"], d["to"], " -> ".join(d["path"])] for i, d in enumerate(contradictions)])

    if repeated:
        write_csv("duplicate_edges", ["Source", "Target", "Occurrences"],
                  [(a, b, count) for (a, b), count in repeated.items() if count > 1])

    if reflexive_links:
        write_csv("self_links", ["CUI", "Relation"], list(reflexive_links))

    write_csv("run_statistics", ["Metric", "Value"], list(stats.items()))


def main():
    parser = argparse.ArgumentParser(description="Detect UMLS Ontology Inconsistencies")
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to MRREL.RRF file")
    parser.add_argument("-t", "--check", choices=["parent-child", "broader-than", "both"], required=True)
    args = parser.parse_args()

    start = time.time()
    log.info("Starting relationship parsing...")
    child_links, broader_links, edge_counts, self_refs, rels = load_relationships(args.input)

    summary = {
        "Total Child Links": len(child_links),
        "Total Broader Links": len(broader_links),
        "Unique Relationship Types": len(rels),
        "Reflexive Links Found": len(self_refs),
        "Duplicate Links": sum(1 for v in edge_counts.values() if v > 1)
    }

    # Parent-Child Cycle Detection
    if args.check in ["parent-child", "both"]:
        log.info("Checking for parent-child loops...")
        tree = defaultdict(list)
        for parent, child in child_links:
            tree[parent].append(child)
        t0 = time.time()
        loops = find_hierarchy_cycles(tree)
        summary["Parent-Child Cycles Found"] = len(loops)
        summary["Cycle Detection Time (s)"] = round(time.time() - t0, 2)
        log.info(f"Detected {len(loops)} parent-child loops.")
    else:
        loops = []

    # Broader-Than Violations
    if args.check in ["broader-than", "both"]:
        log.info("Checking broader-than inconsistencies...")
        bt_graph = nx.DiGraph()
        bt_graph.add_edges_from(broader_links)
        t1 = time.time()
        contradictions = identify_broader_issues(bt_graph)
        summary["Broader-Than Violations Found"] = len(contradictions)
        summary["Broader Analysis Time (s)"] = round(time.time() - t1, 2)
        log.info(f"Detected {len(contradictions)} broader-than violations.")
    else:
        contradictions = []

    summary["Total Run Time (s)"] = round(time.time() - start, 2)
    write_reports(loops, contradictions, edge_counts, self_refs, summary)
    log.info("Check complete. Reports saved.")


if __name__ == "__main__":
    main()
