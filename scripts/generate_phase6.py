"""Generate bounded synthetic inputs; hold generator truth outside service mounts."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
import networkx as nx
from blackgrid.contracts import RunConfig
from blackgrid.data.collegemsg import graph_sha256

ROOT = Path(__file__).resolve().parents[1]


def generate(output: Path, sizes=(100, 300, 1000), seed=20261023):
    if output.exists():
        raise ValueError("output exists; preserve prior inputs and choose a new directory")
    if any(type(n) is not int or not 10 <= n <= 1000 for n in sizes):
        raise ValueError("benchmark sizes must fit the existing 1000-node cap")
    public, truth = output/"public", output/"truth"
    public.mkdir(parents=True)
    truth.mkdir()
    manifests = []
    for n in sizes:
        for offset, name in enumerate(("erdos_renyi", "barabasi_albert", "watts_strogatz", "stochastic_block", "temporal")):
            local_seed = seed+n*10+offset
            rng = random.Random(local_seed)
            labels = None
            if name == "erdos_renyi":
                graph = nx.gnp_random_graph(n, 6/(n-1), seed=local_seed)
            elif name == "barabasi_albert":
                graph = nx.barabasi_albert_graph(n, 2, seed=local_seed)
            elif name == "watts_strogatz":
                graph = nx.watts_strogatz_graph(n, 6, .15, seed=local_seed)
            elif name == "stochastic_block":
                graph = nx.stochastic_block_model([n//2,n-n//2], [[8/n,.5/n],[.5/n,8/n]], seed=local_seed)
                labels = {str(i+1): int(i >= n//2) for i in range(n)}
            else:
                graph = nx.Graph()
                pairs, events = [], []
                for i in range(4*n):
                    if pairs and rng.random() < .65:
                        a,b = rng.choice(pairs)
                    else:
                        a,b = sorted(rng.sample(range(n), 2))
                        pairs.append((a,b))
                    events.append((a,b,1_000_000+i*60))
                history, future = events[:3*n], events[3*n:]
                graph.add_edges_from((a,b) for a,b,_ in history)
            if name != "temporal":
                history = [(a,b,1_000_000+i*30) for i,(a,b) in enumerate(sorted(graph.edges()))]
                future = []
            active = nx.Graph()
            active.add_edges_from((a,b) for a,b,_ in history)
            if active.number_of_edges() > 10000:
                raise ValueError("frozen generator exceeded edge cap; retain failure, do not resample")
            stem = f"{name}-{n}"
            path = public/(stem+".events.txt")
            path.write_text("".join(f"{a+1} {b+1} {t}\n" for a,b,t in history), encoding="utf-8")
            projected = nx.relabel_nodes(active, {i:i+1 for i in active})
            manifest = dict(version="production-phase6-v1", origin="synthetic", family=name,
                requested_nodes=n, active_nodes=len(active), edges=active.number_of_edges(), seed=local_seed,
                rights="independently_generated_local", license_note="Independently generated fixtures; no third-party dataset",
                data_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), projection_sha256=graph_sha256(projected),
                networkx=nx.__version__, temporal_process="65% reuse a previously sampled pair, otherwise uniform new draw" if name == "temporal" else None,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            raw = json.dumps(manifest, indent=2, sort_keys=True).encode()
            path.with_suffix(".manifest.json").write_bytes(raw)
            config = json.loads((ROOT/"configs/collegemsg_sprint01.json").read_bytes())
            case_id = "blackgrid-synthetic-"+hashlib.sha256((stem+str(local_seed)).encode()).hexdigest()[:12]
            config["dataset"].update(dataset_id=case_id, path=path.name,
                sha256=manifest["data_sha256"], source_url="blackgrid-synthetic-v1:"+hashlib.sha256(raw).hexdigest(),
                citations=["Independently generated production-phase6-v1 engineering fixture; not CollegeMsg evidence"],
                rights_decision="PHASE6-SYNTHETIC-OWNED-v1", redistribution_allowed=True)
            config["experiment"].update(experiment_id="benchmark-"+case_id, graph_id=case_id,
                hypothesis="Exploratory synthetic engineering fixture; not a real-data confirmatory claim",
                competing_explanations=["Generator structure and finite-sample variability"],
                null_replicates=19, optimizer_restarts=1, seed=local_seed)
            config["experiment"]["sensitivity"]["replicates"] = 1
            config["deadline_s"] = 120
            validated = RunConfig.model_validate(config)
            (public/(stem+".json")).write_text(validated.model_dump_json(indent=2), encoding="utf-8")
            (truth/(stem+".json")).write_text(json.dumps(dict(planted_membership=labels,
                future_events=[(a+1,b+1,t) for a,b,t in future], future_cutoff=history[-1][2]+1, note="Generator truth; never mounted in worker or used to tune this pilot")), encoding="utf-8")
            manifests.append(manifest)
    (output/"manifest.json").write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    return manifests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"tmp/phase6-inputs-v1")
    args = parser.parse_args()
    print(json.dumps({"generated": len(generate(args.output)), "origin": "synthetic", "truth_outside_runtime": True}))
