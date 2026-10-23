"""Bounded CPU profile of the existing frozen synthetic graph-tool path."""
import cProfile
import hashlib
import json
import pstats
import resource
import time
from pathlib import Path
from blackgrid.contracts import RunConfig
from blackgrid.data.collegemsg import build_graph
from blackgrid.agent.tools import ToolContext,execute


def main():
    root=Path('/bench/public')
    config_path=root/'stochastic_block-100.json'
    config=RunConfig.model_validate_json(config_path.read_bytes())
    built=build_graph(root,config)
    ctx=ToolContext(built.graph,built.record,config.experiment,cache_dir=None)
    ctx.sensitivity_null_replicates=19
    profiler=cProfile.Profile()
    started=time.perf_counter()
    profiler.enable()
    for tool in ('profile_graph','community_test','edge_removal_sensitivity'):
        execute({'tool':tool,'args':{}},ctx)
    profiler.disable()
    stats=pstats.Stats(profiler)
    rows=[dict(module=Path(file).name,line=line,function=name,calls=nc,primitive_calls=cc,
        self_seconds=tt,cumulative_seconds=ct) for (file,line,name),(cc,nc,tt,ct,_) in stats.stats.items()]
    report=dict(version='production-phase8-v1',origin=built.record.origin.value,mode='mock',
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),data_sha256=config.dataset.sha256,
        nodes=len(built.graph),edges=built.graph.number_of_edges(),wall_seconds=time.perf_counter()-started,
        tools=[r.model_dump(mode='json') for r in ctx.calls],
        top_cumulative=sorted(rows,key=lambda r:r['cumulative_seconds'],reverse=True)[:30],
        top_self=sorted(rows,key=lambda r:r['self_seconds'],reverse=True)[:30],
        max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        limitation='instrumented profile; not a before/after latency sample',real_provider_calls=0,actual_usd=0)
    Path('/evidence/profile_baseline.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('nodes','edges','wall_seconds','max_rss_bytes')}))


if __name__=='__main__': main()
