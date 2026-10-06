import argparse
import asyncio
import json
import os
from pathlib import Path

from .common import ROOT, digest, envelope, write_json
from .dataset import load_manifest


def main():
    parser = argparse.ArgumentParser(description="ConceptLens Phase 9 evaluation (no normal development DB access)")
    sub = parser.add_subparsers(dest="command",required=True)
    default_manifest = ROOT/"evaluation/datasets/grounding.json"
    for command in ("validate-dataset","grounding"):
        p = sub.add_parser(command)
        p.add_argument("--manifest",type=Path,default=default_manifest)
        if command=="grounding":
            p.add_argument("--split",choices=["development","test"],default="test")
            p.add_argument("--out",type=Path,default=ROOT/"evaluation/reports/grounding.json")
    p = sub.add_parser("simulate")
    p.add_argument("--config",type=Path,default=ROOT/"evaluation/configuration/simulation.json")
    p.add_argument("--bank",type=Path,default=ROOT/"evaluation/datasets/items.json")
    p.add_argument("--out",type=Path,default=ROOT/"evaluation/reports/simulation.json")
    p = sub.add_parser("report")
    p.add_argument("--grounding",type=Path,default=ROOT/"evaluation/reports/grounding.json")
    p.add_argument("--simulation",type=Path,default=ROOT/"evaluation/reports/simulation.json")
    p.add_argument("--out",type=Path,default=ROOT/"evaluation/reports/judge")
    p = sub.add_parser("db-check")
    p.add_argument("--out",type=Path,default=ROOT/"evaluation/reports/database-check.json")
    args = parser.parse_args()
    if args.command in {"validate-dataset","grounding"}:
        manifest = load_manifest(args.manifest)
        if args.command=="validate-dataset":
            print(json.dumps({"valid":True,"version":manifest.version,"cases":len(manifest.cases),"source_hashes_verified":True}))
            return
        from .grounding import run
        payload = asyncio.run(run(manifest,args.manifest,args.split,os.getenv("CONCEPTLENS_EVAL_ADMIN_URL")))
        result = envelope(payload,{"split":args.split,"manifest_sha256":digest(args.manifest),"top_k":10},manifest.version)
    elif args.command=="simulate":
        from .simulation import Config, load_bank, run
        config = Config.model_validate(json.loads(args.config.read_text()))
        bank = load_bank(args.bank,config.sessions)
        payload = asyncio.run(run(config,bank))
        result = envelope(payload,{**config.model_dump(),"bank_sha256":digest(args.bank)},bank["version"])
    elif args.command=="report":
        from .reporting import build_report
        print(json.dumps(build_report(json.loads(args.grounding.read_text()),json.loads(args.simulation.read_text()),args.out)))
        return
    else:
        from .database import check_lifecycle
        admin = os.getenv("CONCEPTLENS_EVAL_ADMIN_URL")
        if not admin: parser.error("set CONCEPTLENS_EVAL_ADMIN_URL to an explicit local /postgres admin URL")
        result = {"success_path":asyncio.run(check_lifecycle(admin)),"failure_path":asyncio.run(check_lifecycle(admin,fail_inside=True))}
    write_json(args.out,result)
    print(json.dumps({"written":str(args.out),"label":result.get("payload",{}).get("label")}))


if __name__ == "__main__":
    main()
