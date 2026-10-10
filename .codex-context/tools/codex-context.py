#!/usr/bin/env python3
"""Codex Context Optimizer: analyze repositories and measure local Codex usage."""

from __future__ import annotations
import argparse, datetime as dt, json, os, pathlib, shutil, subprocess, sys
from dataclasses import dataclass, asdict
from typing import Any

STATE_DIR = ".codex-context"
CODE_EXTS = {".py",".js",".jsx",".ts",".tsx",".go",".rs",".java",".kt",".c",".h",".cc",".cpp",".hpp",".cs",".php",".rb",".swift",".sh",".sql",".vue",".svelte"}
NOISE_DIRS = {"node_modules","vendor",".venv","venv","dist","build","coverage",".cache","__pycache__",".pytest_cache",".mypy_cache",".next",".nuxt",".turbo","target","logs","log","tmp","temp"}

@dataclass
class Usage:
    responses:int=0
    input_tokens:int=0
    cached_input_tokens:int=0
    cache_write_input_tokens:int=0
    output_tokens:int=0
    reasoning_output_tokens:int=0
    total_tokens:int=0
    max_last_input_tokens:int=0
    max_context_window:int=0
    sessions:int=0
    source:str="none"

    @property
    def non_cached_input_tokens(self):
        return max(0, self.input_tokens-self.cached_input_tokens)

    @property
    def cached_ratio(self):
        return self.cached_input_tokens/self.input_tokens if self.input_tokens else 0.0

    @property
    def avg_total_per_response(self):
        return self.total_tokens/self.responses if self.responses else 0.0

    def minus(self, other):
        return Usage(
            responses=max(0,self.responses-other.responses),
            input_tokens=max(0,self.input_tokens-other.input_tokens),
            cached_input_tokens=max(0,self.cached_input_tokens-other.cached_input_tokens),
            cache_write_input_tokens=max(0,self.cache_write_input_tokens-other.cache_write_input_tokens),
            output_tokens=max(0,self.output_tokens-other.output_tokens),
            reasoning_output_tokens=max(0,self.reasoning_output_tokens-other.reasoning_output_tokens),
            total_tokens=max(0,self.total_tokens-other.total_tokens),
            max_last_input_tokens=self.max_last_input_tokens,
            max_context_window=self.max_context_window,
            sessions=max(0,self.sessions-other.sessions),
            source=self.source)

def run(cmd, cwd=None):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "command failed")
    return p.stdout

def root_for(path=None):
    base=pathlib.Path(path or ".").expanduser().resolve()
    try:
        return pathlib.Path(run(["git","rev-parse","--show-toplevel"],base).strip())
    except Exception:
        return base

def est_tokens(n):
    return max(1,round(n/4))

def tracked_files(root):
    try:
        raw=subprocess.run(["git","ls-files","-z"],cwd=root,stdout=subprocess.PIPE,check=True).stdout
        return [root/p.decode("utf-8","replace") for p in raw.split(b"\0") if p]
    except Exception:
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]

def cmd_analyze(a):
    root=root_for(a.repo)
    files=tracked_files(root)
    code=[p for p in files if p.suffix.lower() in CODE_EXTS]
    source_bytes=0; large=[]
    for p in code:
        try: size=p.stat().st_size
        except OSError: continue
        source_bytes+=size
        if size>=a.large_file_bytes:
            large.append((size,str(p.relative_to(root))))
    agents=root/"AGENTS.md"; atlas=root/"atlas-map.md"
    ab=agents.stat().st_size if agents.exists() else 0
    mb=atlas.stat().st_size if atlas.exists() else 0
    warnings=[]
    if not agents.exists(): warnings.append("No root AGENTS.md found.")
    elif est_tokens(ab)>a.agents_token_warn: warnings.append("AGENTS.md is large persistent context.")
    if not atlas.exists(): warnings.append("No atlas-map.md found.")
    elif est_tokens(mb)>a.atlas_token_warn: warnings.append("atlas-map.md is larger than the recommended bounded map.")
    if large: warnings.append(str(len(large))+" tracked source file(s) are unusually large.")
    report={
      "repo":str(root),"tracked_files":len(files),"source_files":len(code),
      "source_bytes":source_bytes,"estimated_source_tokens":est_tokens(source_bytes),
      "agents_exists":agents.exists(),"estimated_agents_tokens":est_tokens(ab) if ab else 0,
      "atlas_exists":atlas.exists(),"estimated_atlas_tokens":est_tokens(mb) if mb else 0,
      "noise_dirs_present":sorted(x for x in NOISE_DIRS if (root/x).exists()),
      "large_source_files":[{"path":p,"bytes":s} for s,p in sorted(large,reverse=True)[:20]],
      "warnings":warnings}
    if a.json:
        print(json.dumps(report,indent=2,ensure_ascii=False)); return 0
    print("Repository context analysis\n---------------------------")
    print("Repo:                    "+str(root))
    print("Tracked files:           "+f"{len(files):,}")
    print("Source files:            "+f"{len(code):,}")
    print("Estimated source tokens: "+f"{report['estimated_source_tokens']:,}"+" (rough estimate)")
    print("AGENTS.md:               "+("yes (~"+f"{report['estimated_agents_tokens']:,}"+" tokens)" if agents.exists() else "no"))
    print("atlas-map.md:            "+("yes (~"+f"{report['estimated_atlas_tokens']:,}"+" tokens)" if atlas.exists() else "no"))
    if report["noise_dirs_present"]: print("Heavy dirs present:      "+", ".join(report["noise_dirs_present"]))
    if warnings:
        print("\nWarnings")
        for w in warnings: print("- "+w)
    else: print("\nNo obvious persistent-context issues detected.")
    return 0

def session_path():
    return pathlib.Path(os.environ.get("CODEX_HOME","~/.codex")).expanduser()/"sessions"

def files_under(base):
    return sorted(base.rglob("*.jsonl")) if base.exists() else []

def session_cwd(path):
    """Return the working directory recorded by Codex for one rollout file."""
    try:
        fh=path.open("r",encoding="utf-8",errors="replace")
    except OSError:
        return None
    with fh:
        for line_no,line in enumerate(fh,1):
            if line_no > 250:
                break
            try:
                obj=json.loads(line)
            except Exception:
                continue
            if not isinstance(obj,dict):
                continue
            payload=obj.get("payload")
            if not isinstance(payload,dict):
                continue
            if obj.get("type")=="session_meta":
                cwd=payload.get("cwd")
                if not cwd and isinstance(payload.get("meta"),dict):
                    cwd=payload["meta"].get("cwd")
                if isinstance(cwd,str) and cwd.strip():
                    return cwd.strip()
            # Fallback for builds where turn_context carries the usable cwd.
            if obj.get("type")=="turn_context":
                cwd=payload.get("cwd")
                if isinstance(cwd,str) and cwd.strip():
                    return cwd.strip()
    return None

def normalized_path(value):
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(str(value)))))
    except Exception:
        return os.path.normcase(os.path.abspath(os.path.expanduser(str(value))))

def path_within(child,parent):
    child=normalized_path(child); parent=normalized_path(parent)
    try:
        return os.path.commonpath([child,parent])==parent
    except (ValueError,OSError):
        return child==parent

def session_matches_project(path,root):
    if root is None:
        return True
    cwd=session_cwd(path)
    if not cwd:
        return False
    # Sessions started from the project root or one of its subdirectories belong
    # to this project. Parent-directory sessions are intentionally excluded.
    return path_within(cwd,root)

def session_files(base,root=None):
    files=files_under(base)
    if root is None:
        return files
    return [p for p in files if session_matches_project(p,root)]

def usage_dict(d):
    def n(s,c):
        v=d.get(s,d.get(c,0)); return int(v or 0) if isinstance(v,(int,float)) else 0
    return Usage(input_tokens=n("input_tokens","inputTokens"),cached_input_tokens=n("cached_input_tokens","cachedInputTokens"),
      cache_write_input_tokens=n("cache_write_input_tokens","cacheWriteInputTokens"),output_tokens=n("output_tokens","outputTokens"),
      reasoning_output_tokens=n("reasoning_output_tokens","reasoningOutputTokens"),total_tokens=n("total_tokens","totalTokens"))

def modern_record(obj):
    if not isinstance(obj,dict): return None,None
    if obj.get("type")=="token_usage_record":
        p=obj.get("payload") if isinstance(obj.get("payload"),dict) else obj
        u=p.get("usage") if isinstance(p.get("usage"),dict) else None
        return p.get("response_id") or p.get("responseId"),u
    p=obj.get("payload")
    if isinstance(p,dict) and p.get("type")=="token_usage_record":
        return p.get("response_id") or p.get("responseId"), p.get("usage") if isinstance(p.get("usage"),dict) else None
    return None,None

def token_count(obj):
    if not isinstance(obj,dict): return None,None,0
    p=obj.get("payload")
    if not isinstance(p,dict) or p.get("type")!="token_count": return None,None,0
    info=p.get("info") if isinstance(p.get("info"),dict) else {}
    return info.get("total_token_usage"),info.get("last_token_usage"),int(info.get("model_context_window") or 0)

def collect(base,root=None):
    modern=Usage(source="token_usage_record"); seen=set(); mfiles=set()
    final={}; peaks={}; window=0
    for path in session_files(base,root):
        try:
            fh=path.open("r",encoding="utf-8",errors="replace")
        except OSError: continue
        with fh:
            for line_no,line in enumerate(fh,1):
                try: obj=json.loads(line)
                except Exception: continue
                rid,ud=modern_record(obj)
                if isinstance(ud,dict):
                    u=usage_dict(ud); key=str(rid) if rid is not None else str(path)+":"+str(line_no)
                    if key not in seen:
                        seen.add(key); modern.responses+=1; mfiles.add(path)
                        modern.input_tokens+=u.input_tokens; modern.cached_input_tokens+=u.cached_input_tokens
                        modern.cache_write_input_tokens+=u.cache_write_input_tokens; modern.output_tokens+=u.output_tokens
                        modern.reasoning_output_tokens+=u.reasoning_output_tokens
                        modern.total_tokens+=u.total_tokens or u.input_tokens+u.output_tokens
                cum,last,w=token_count(obj)
                if isinstance(cum,dict): final[path]=usage_dict(cum)
                if isinstance(last,dict): peaks[path]=max(peaks.get(path,0),usage_dict(last).input_tokens)
                window=max(window,w)
    if modern.responses:
        modern.sessions=len(mfiles); modern.max_last_input_tokens=max(peaks.values(),default=0); modern.max_context_window=window
        return modern
    fallback=Usage(source="token_count cumulative fallback")
    for u in final.values():
        fallback.input_tokens+=u.input_tokens; fallback.cached_input_tokens+=u.cached_input_tokens
        fallback.cache_write_input_tokens+=u.cache_write_input_tokens; fallback.output_tokens+=u.output_tokens
        fallback.reasoning_output_tokens+=u.reasoning_output_tokens; fallback.total_tokens+=u.total_tokens or u.input_tokens+u.output_tokens
    fallback.sessions=len(final); fallback.max_last_input_tokens=max(peaks.values(),default=0); fallback.max_context_window=window
    return fallback

def print_usage(u,title="Codex usage"):
    print(title+"\n"+"-"*len(title))
    print("Source:                  "+u.source)
    print("Sessions:                "+f"{u.sessions:,}")
    if u.responses: print("Unique responses:        "+f"{u.responses:,}")
    print("Input tokens:            "+f"{u.input_tokens:,}")
    print("Cached input:            "+f"{u.cached_input_tokens:,}"+" ("+f"{u.cached_ratio:.1%}"+" of input)")
    if u.cache_write_input_tokens: print("Cache-write input:       "+f"{u.cache_write_input_tokens:,}")
    print("Non-cached input:        "+f"{u.non_cached_input_tokens:,}")
    print("Output tokens:           "+f"{u.output_tokens:,}")
    print("Reasoning output:        "+f"{u.reasoning_output_tokens:,}"+" (subset of output)")
    print("Total tokens:            "+f"{u.total_tokens:,}")
    if u.responses: print("Avg total / response:    "+f"{u.avg_total_per_response:,.0f}")
    if u.max_last_input_tokens: print("Peak last-turn input:    "+f"{u.max_last_input_tokens:,}")
    if u.max_context_window:
        print("Reported context window: "+f"{u.max_context_window:,}")
        print("Peak context occupancy:  "+f"{u.max_last_input_tokens/u.max_context_window:.1%}")

def cmd_usage(a):
    base=pathlib.Path(a.sessions).expanduser() if a.sessions else session_path()
    root=root_for(a.repo) if a.repo else None
    u=collect(base,root)
    if a.json:
        d=asdict(u); d.update({"non_cached_input_tokens":u.non_cached_input_tokens,"cached_ratio":u.cached_ratio,
          "avg_total_per_response":u.avg_total_per_response,"sessions_path":str(base),
          "scope_repo":str(root) if root else None})
        print(json.dumps(d,indent=2)); return 0
    print_usage(u)
    if root: print("Project scope:            "+str(root))
    if u.source.startswith("token_count"): print("\nNote: using final cumulative token_count per session because modern token_usage_record entries were not found.")
    print("\nLocal telemetry is not an authoritative invoice or plan-quota calculation.")
    return 0

def bench_path(root,name):
    p=root/STATE_DIR/"benchmarks"; p.mkdir(parents=True,exist_ok=True)
    safe="".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    return p/(safe+".json")

def snap(base,root=None):
    return {"captured_at":dt.datetime.now(dt.timezone.utc).isoformat(),"sessions_path":str(base),
      "scope_repo":str(root) if root else None,"usage":asdict(collect(base,root))}

def cmd_start(a):
    root=root_for(a.repo); base=pathlib.Path(a.sessions).expanduser() if a.sessions else session_path()
    p=bench_path(root,a.name+".start"); p.write_text(json.dumps(snap(base,root),indent=2),encoding="utf-8")
    print("Benchmark '"+a.name+"' started. Run the task, then benchmark-end with the same name.")
    return 0

def cmd_end(a):
    root=root_for(a.repo); base=pathlib.Path(a.sessions).expanduser() if a.sessions else session_path()
    sp=bench_path(root,a.name+".start")
    if not sp.exists(): print("Missing start snapshot.",file=sys.stderr); return 2
    start=json.loads(sp.read_text()); end=snap(base,root)
    eu=Usage(**end["usage"]); su=Usage(**start["usage"]); delta=eu.minus(su)
    rp=bench_path(root,a.name+".result"); rp.write_text(json.dumps({"name":a.name,"start":start,"end":end,"delta":asdict(delta)},indent=2),encoding="utf-8")
    print_usage(delta,"Benchmark result: "+a.name); return 0

def load_result(root,name):
    p=bench_path(root,name+".result")
    if not p.exists(): raise FileNotFoundError(str(p))
    return Usage(**json.loads(p.read_text())["delta"])

def change(b,a):
    return "n/a" if not b else f"{((a-b)/b)*100:+.1f}%"

def cmd_compare(a):
    root=root_for(a.repo)
    try: b=load_result(root,a.before); n=load_result(root,a.after)
    except FileNotFoundError as e: print("Missing benchmark: "+str(e),file=sys.stderr); return 2
    rows=[("Responses",b.responses,n.responses),("Input tokens",b.input_tokens,n.input_tokens),("Cached input",b.cached_input_tokens,n.cached_input_tokens),
      ("Non-cached input",b.non_cached_input_tokens,n.non_cached_input_tokens),("Output tokens",b.output_tokens,n.output_tokens),("Total tokens",b.total_tokens,n.total_tokens)]
    print("Benchmark comparison: "+a.before+" -> "+a.after)
    print(f"{'Metric':<22} {'Before':>14} {'After':>14} {'Change':>12}")
    for label,x,y in rows: print(f"{label:<22} {x:>14,} {y:>14,} {change(x,y):>12}")
    print("\nQuality gate: token reduction is only a success if correctness, tests and task scope are preserved.")
    return 0


def latest_session_health(base,root=None):
    files=session_files(base,root)
    if not files:
        return None
    try:
        path=max(files,key=lambda p:p.stat().st_mtime)
    except Exception:
        return None

    usage=Usage(source="latest-session")
    seen=set()
    peak_last=0
    window=0
    last_cumulative=None

    try:
        fh=path.open("r",encoding="utf-8",errors="replace")
    except OSError:
        return None

    with fh:
        for line_no,line in enumerate(fh,1):
            try:
                obj=json.loads(line)
            except Exception:
                continue

            rid,ud=modern_record(obj)
            if isinstance(ud,dict):
                u=usage_dict(ud)
                key=str(rid) if rid is not None else str(line_no)
                if key not in seen:
                    seen.add(key)
                    usage.responses+=1
                    usage.input_tokens+=u.input_tokens
                    usage.cached_input_tokens+=u.cached_input_tokens
                    usage.cache_write_input_tokens+=u.cache_write_input_tokens
                    usage.output_tokens+=u.output_tokens
                    usage.reasoning_output_tokens+=u.reasoning_output_tokens
                    usage.total_tokens+=u.total_tokens or u.input_tokens+u.output_tokens

            cumulative,last,w=token_count(obj)
            if isinstance(cumulative,dict):
                last_cumulative=usage_dict(cumulative)
            if isinstance(last,dict):
                peak_last=max(peak_last,usage_dict(last).input_tokens)
            window=max(window,w)

    # Some Codex builds only expose cumulative token_count in a session.
    if usage.responses==0 and last_cumulative is not None:
        usage=last_cumulative
        usage.source="latest-session cumulative fallback"

    usage.sessions=1
    usage.max_last_input_tokens=peak_last
    usage.max_context_window=window
    return {
        "path":str(path),
        "usage":usage,
        "occupancy":(peak_last/window) if peak_last and window else 0.0,
    }

def pressure_label(occupancy):
    if occupancy >= 0.90:
        return "CRITICAL"
    if occupancy >= 0.80:
        return "HIGH"
    if occupancy >= 0.65:
        return "ELEVATED"
    return "NORMAL"

def report_history_path(root):
    return root/STATE_DIR/"report-history.jsonl"

def read_last_report(root):
    p=report_history_path(root)
    if not p.exists():
        return None
    last=None
    try:
        with p.open("r",encoding="utf-8",errors="replace") as fh:
            for line in fh:
                try:
                    last=json.loads(line)
                except Exception:
                    continue
    except OSError:
        return None
    return last

def append_report_history(root,record):
    p=report_history_path(root)
    p.parent.mkdir(parents=True,exist_ok=True)
    try:
        with p.open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(record,ensure_ascii=False)+"\\n")
    except OSError:
        pass

def cmd_report(a):
    root=root_for(a.repo)
    base=pathlib.Path(a.sessions).expanduser() if a.sessions else session_path()
    current=collect(base,root)

    baseline=None
    baseline_label=None
    baseline_file=root/STATE_DIR/"install-baseline.json"

    if baseline_file.exists():
        try:
            data=json.loads(baseline_file.read_text(encoding="utf-8-sig"))
            scope=data.get("scope_repo")
            if scope and normalized_path(scope)==normalized_path(root):
                raw=data.get("usage",data)
                baseline=Usage(**{k:v for k,v in raw.items() if k in Usage.__dataclass_fields__})
                baseline_label="project install baseline"
        except Exception:
            baseline=None

    # Older baselines/benchmarks were global across all Codex projects.
    # Never mix them into a project-scoped report.

    if baseline is None:
        baseline_file.parent.mkdir(parents=True,exist_ok=True)
        baseline_file.write_text(json.dumps({
            "captured_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "scope_repo":str(root),
            "usage":asdict(current),
            "note":"Project-scoped baseline created automatically from Codex session cwd metadata."
        },indent=2),encoding="utf-8")
        print("Optimizer report")
        print("----------------")
        print("Project-scoped baseline created now.")
        print("Project:                  "+str(root))
        print("Matched sessions:         "+f"{current.sessions:,}")
        print("Current responses:        "+f"{current.responses:,}")
        print("Current avg/response:     "+(f"{current.avg_total_per_response:,.0f}" if current.responses else "n/a"))
        print()
        print("Keep using Codex normally. Run this same report command later.")
        print("No manual benchmark-start/benchmark-end is required.")
        return 0

    after=current.minus(baseline)
    before_avg=baseline.avg_total_per_response
    after_avg=after.avg_total_per_response
    saving=None
    if before_avg and after_avg:
        saving=((before_avg-after_avg)/before_avg)*100

    latest=latest_session_health(base,root)
    occupancy=latest["occupancy"] if latest else 0.0
    pressure=pressure_label(occupancy)

    previous=read_last_report(root)

    print("Optimizer report")
    print("----------------")
    print("Project:                  "+str(root))
    print("Matched sessions:         "+f"{current.sessions:,}")
    print("Baseline:                 "+str(baseline_label))
    print("Before responses:         "+f"{baseline.responses:,}")
    print("After responses:          "+f"{after.responses:,}")
    print("Before avg/response:      "+(f"{before_avg:,.0f}" if before_avg else "n/a"))
    print("After avg/response:       "+(f"{after_avg:,.0f}" if after_avg else "n/a"))

    if saving is not None:
        print("Estimated change:         "+f"{-saving:+.1f}%")
        if saving > 0:
            print("Estimated saving:         "+f"{saving:.1f}% per response")
        else:
            print("Estimated saving:         no reduction detected yet")

    print("After total tokens:       "+f"{after.total_tokens:,}")
    print("After cached input:       "+f"{after.cached_input_tokens:,}"+" ("+f"{after.cached_ratio:.1%}"+" of input)")

    if latest:
        lu=latest["usage"]
        print()
        print("Latest session")
        print("--------------")
        print("Responses:                "+f"{lu.responses:,}")
        if lu.responses:
            print("Avg tokens/response:      "+f"{lu.avg_total_per_response:,.0f}")
        if occupancy:
            print("Peak context occupancy:   "+f"{occupancy:.1%}")
        print("Context pressure:         "+pressure)

    if previous and saving is not None and isinstance(previous.get("saving_pct"),(int,float)):
        drift=saving-float(previous["saving_pct"])
        if abs(drift) >= 0.1:
            direction="improved" if drift>0 else "declined"
            print()
            print("Since last report:        "+direction+" "+f"{abs(drift):.1f}"+" percentage points")

    if after.responses < 10:
        confidence="LOW — collect more post-optimizer responses"
    elif after.responses < 30:
        confidence="EARLY TREND"
    else:
        confidence="TREND"

    print()
    print("Confidence: "+confidence)
    print("This is a live before/after trend, not a controlled A/B test.")

    if pressure in {"HIGH","CRITICAL"}:
        print()
        print("Recommended action")
        print("------------------")
        print("This session is using a large share of the context window.")
        print("Create a compact handoff and continue in a fresh chat:")
        print("  python .codex-context\\tools\\codex-context.py fresh-start --repo .")
    append_report_history(root,{
        "captured_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "before_responses":baseline.responses,
        "after_responses":after.responses,
        "before_avg":before_avg,
        "after_avg":after_avg,
        "saving_pct":saving,
        "cached_ratio":after.cached_ratio,
        "latest_occupancy":occupancy,
        "pressure":pressure,
    })
    return 0

def status_paths(root):
    try: out=run(["git","status","--porcelain=v1"],root)
    except Exception: return []
    return [line[3:] for line in out.splitlines() if len(line)>=4]

def cmd_handoff(a):
    root=root_for(a.repo)
    out=root/(a.output or STATE_DIR+"/HANDOFF.md")
    out.parent.mkdir(parents=True,exist_ok=True)

    try:
        branch=run(["git","branch","--show-current"],root).strip() or "(detached)"
    except Exception:
        branch="(unknown)"
    try:
        recent=run(["git","log","-5","--oneline","--decorate=no"],root).strip()
    except Exception:
        recent="(unavailable)"
    try:
        diffstat=run(["git","diff","--stat"],root).strip()
    except Exception:
        diffstat="(unavailable)"
    changed=status_paths(root)

    agents="AGENTS.md" if (root/"AGENTS.md").exists() else "(missing)"
    atlas="atlas-map.md" if (root/"atlas-map.md").exists() else "(missing)"

    lines=[
      "# Codex handoff","",
      "Generated: "+dt.datetime.now(dt.timezone.utc).isoformat(),
      "Branch: "+branch,"",
      "## Resume instructions","",
      "- Read this file first.",
      "- Read "+agents+" and "+atlas+" if present.",
      "- Preserve existing working-tree changes.",
      "- Use the smallest relevant source set first, then expand whenever correctness requires it.","",
      "## Working tree","",
    ]
    lines += ["- "+p for p in changed] if changed else ["- clean working tree"]
    lines += ["","## Diff summary","","~~~text",diffstat or "(no unstaged diff)","~~~","",
      "## Recent commits","","~~~text",recent,"~~~","",
      "## What the next chat should establish","",
      "- Confirm the current task goal from the user's first message.",
      "- Reuse decisions visible in changed files and git history; do not invent missing decisions.",
      "- Run the narrowest relevant validation before broad checks.","",
      "Keep this handoff compact. Do not paste full logs, full diffs, or large source files here.",""
    ]
    out.write_text("\n".join(lines),encoding="utf-8")
    print("Wrote compact handoff: "+str(out))
    return 0

def cmd_fresh_start(a):
    rc=cmd_handoff(a)
    if rc:
        return rc
    root=root_for(a.repo)
    print()
    print("Fresh-chat package ready.")
    print("-------------------------")
    print("Open a NEW Codex chat in this project and send:")
    print()
    print("Read .codex-context/HANDOFF.md, AGENTS.md, and atlas-map.md if present.")
    print("Preserve the existing working tree, then continue with my task.")
    print()
    print("This avoids carrying the full old conversation into the next task.")
    return 0

def cmd_doctor(a):
    root=root_for(a.repo)
    base=pathlib.Path(a.sessions).expanduser() if a.sessions else session_path()
    latest=latest_session_health(base,root)

    agents=root/"AGENTS.md"
    atlas=root/"atlas-map.md"
    print("Context optimizer doctor")
    print("------------------------")
    print("Repository:              "+str(root))
    print("AGENTS.md:               "+("OK" if agents.exists() else "MISSING"))
    if agents.exists():
        print("AGENTS approx tokens:    "+f"{est_tokens(agents.stat().st_size):,}")
    print("atlas-map.md:            "+("OK" if atlas.exists() else "MISSING"))
    if atlas.exists():
        print("Atlas approx tokens:     "+f"{est_tokens(atlas.stat().st_size):,}")
    print("Atlas CLI:               "+("available" if shutil.which("atlas") else "not found"))
    print("CatchUp CLI:             "+("available (optional integration)" if shutil.which("catchup") else "not installed (optional)"))

    if latest:
        occ=latest["occupancy"]
        print("Latest context pressure: "+pressure_label(occ)+((" ("+f"{occ:.1%}"+")") if occ else ""))
        if pressure_label(occ) in {"HIGH","CRITICAL"}:
            print()
            print("Action: run fresh-start before the next substantial task.")

    print()
    print("No third-party handoff/compression tool is required.")
    print("Optional tools such as CatchUp or Codex Compressor can be evaluated separately.")
    return 0

def parser():
    p=argparse.ArgumentParser(prog="codex-context",description="Measure and reduce unnecessary Codex context usage.")
    s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("analyze"); x.add_argument("--repo"); x.add_argument("--json",action="store_true"); x.add_argument("--large-file-bytes",type=int,default=204800); x.add_argument("--agents-token-warn",type=int,default=2500); x.add_argument("--atlas-token-warn",type=int,default=3000); x.set_defaults(fn=cmd_analyze)
    x=s.add_parser("usage"); x.add_argument("--repo"); x.add_argument("--sessions"); x.add_argument("--json",action="store_true"); x.set_defaults(fn=cmd_usage)
    x=s.add_parser("benchmark-start"); x.add_argument("name"); x.add_argument("--repo"); x.add_argument("--sessions"); x.set_defaults(fn=cmd_start)
    x=s.add_parser("benchmark-end"); x.add_argument("name"); x.add_argument("--repo"); x.add_argument("--sessions"); x.set_defaults(fn=cmd_end)
    x=s.add_parser("benchmark-compare"); x.add_argument("before"); x.add_argument("after"); x.add_argument("--repo"); x.set_defaults(fn=cmd_compare)
    x=s.add_parser("report"); x.add_argument("--repo"); x.add_argument("--sessions"); x.set_defaults(fn=cmd_report)
    x=s.add_parser("handoff"); x.add_argument("--repo"); x.add_argument("--output"); x.set_defaults(fn=cmd_handoff)
    x=s.add_parser("fresh-start"); x.add_argument("--repo"); x.add_argument("--output"); x.set_defaults(fn=cmd_fresh_start)
    x=s.add_parser("doctor"); x.add_argument("--repo"); x.add_argument("--sessions"); x.set_defaults(fn=cmd_doctor)
    return p

def main():
    a=parser().parse_args()
    try: return a.fn(a)
    except KeyboardInterrupt: return 130
    except Exception as e: print("error: "+str(e),file=sys.stderr); return 1

if __name__=="__main__":
    raise SystemExit(main())
