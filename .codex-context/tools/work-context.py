#!/usr/bin/env python3
"""Initialize and inspect compact context files for ChatGPT Work projects."""

from __future__ import annotations
import argparse, pathlib, shutil, sys

FILES = ["PROJECT_CONTEXT.md","CURRENT_TASK.md","DECISIONS.md","SOURCE_INDEX.md"]

def root_for(value):
    return pathlib.Path(value or ".").expanduser().resolve()

def est_tokens(size):
    return max(1, round(size/4))

def init_context(args):
    root=root_for(args.repo)
    dest=root/".context"
    dest.mkdir(parents=True,exist_ok=True)
    source=pathlib.Path(__file__).resolve().parent.parent/"templates"/"work"
    created=[]; preserved=[]
    for name in FILES:
        target=dest/name
        if target.exists():
            preserved.append(str(target))
            continue
        template=source/name
        if not template.exists():
            print("Missing template: "+str(template),file=sys.stderr)
            return 2
        shutil.copyfile(template,target)
        created.append(str(target))
    print("Work context initialized.")
    if created:
        print("Created:")
        for p in created: print("- "+p)
    if preserved:
        print("Preserved existing:")
        for p in preserved: print("- "+p)
    print("\nFill only verified project facts. Keep these files compact.")
    return 0

def analyze(args):
    root=root_for(args.repo)
    dest=root/".context"
    print("Work persistent-context analysis")
    print("--------------------------------")
    total=0
    for name in FILES+["HANDOFF.md"]:
        p=dest/name
        if not p.exists():
            print(f"{name:<20} missing")
            continue
        size=p.stat().st_size
        tok=est_tokens(size)
        total+=tok
        status="OK"
        limit=args.task_warn if name in {"CURRENT_TASK.md","HANDOFF.md"} else args.persistent_warn
        if tok>limit: status="WARN"
        print(f"{name:<20} ~{tok:>6,} tokens  {status}")
    print("--------------------------------")
    print(f"Estimated total          ~{total:>6,} tokens")
    print("\nThis is a rough size estimate, not Work billing or model telemetry.")
    return 0

def parser():
    p=argparse.ArgumentParser(prog="work-context",description="Initialize and inspect compact ChatGPT Work context files.")
    s=p.add_subparsers(dest="command",required=True)
    x=s.add_parser("init")
    x.add_argument("--repo")
    x.set_defaults(fn=init_context)
    x=s.add_parser("analyze")
    x.add_argument("--repo")
    x.add_argument("--persistent-warn",type=int,default=1500)
    x.add_argument("--task-warn",type=int,default=1000)
    x.set_defaults(fn=analyze)
    return p

def main():
    a=parser().parse_args()
    return a.fn(a)

if __name__=="__main__":
    raise SystemExit(main())
