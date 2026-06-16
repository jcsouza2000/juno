"""
juno-verify - Verificador independente da trilha JUNO (v0.3).

Modos de uso:

  # Modo bundle (recomendado): arquivo unico do GET /audit/export
  python -m juno_audit.verify export.json

  # Modo legacy v0.1: lista de eventos + pubkeys soltos
  python -m juno_audit.verify eventos.json --pubkeys pubkeys.json --root sha256:...
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from typing import Optional

from .canonical import canonical_json
from .chain import verify_chain
from .merkle import merkle_root, verify_proof
from .signer import verify_event_signature


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK    " if ok else "FALHOU"
    line = f"  [{mark}] {label}"
    if detail:
        line += f"  -- {detail}"
    print(line)
    return ok


def verify_bundle(bundle: dict, check_ots: bool = True) -> bool:
    results: list[bool] = []
    events = bundle["events"]
    anchors = bundle.get("anchors", [])
    proofs = bundle.get("proofs", [])
    pubkeys = bundle.get("pubkeys", {})

    # 1. cadeia + hashes
    ok_chain, errs = verify_chain(events)
    results.append(_check(
        f"[1] cadeia ({len(events)} eventos)", ok_chain,
        "; ".join(errs) if errs else ""))

    # 2. assinaturas Ed25519
    bad = 0
    signed = 0
    for ev in events:
        sig = ev.get("agent_sig")
        agent = ev.get("agent_id")
        if not sig:
            continue
        signed += 1
        pk = pubkeys.get(agent) or pubkeys.get(agent.split(":")[0] if agent else "")
        if not pk or not verify_event_signature(ev, sig, pk):
            bad += 1
    results.append(_check(
        f"[2] assinaturas Ed25519 ({signed} eventos assinados)",
        bad == 0, f"{bad} invalidas" if bad else ""))

    # 3. integridade do bundle
    expected = bundle.get("bundle_hash")
    payload = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    computed = "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
    results.append(_check(
        "[3] integridade do bundle (bundle_hash)", expected == computed,
        "" if expected == computed else "bundle_hash divergente"))

    # 4. raizes Merkle das ancoras
    bad_roots = 0
    for a in anchors:
        if a["event_count"] == 0:
            continue
        if merkle_root(a["event_hashes"]) != a["merkle_root"]:
            bad_roots += 1
    results.append(_check(
        f"[4] raizes Merkle ({len(anchors)} ancoras)",
        bad_roots == 0, f"{bad_roots} raizes nao batem" if bad_roots else ""))

    # 5. provas de inclusao
    bad_proofs = 0
    for p in proofs:
        proof_tuples = [(item["side"], item["hash"]) for item in p["proof"]]
        if not verify_proof(p["event_hash"], proof_tuples, p["merkle_root"]):
            bad_proofs += 1
    results.append(_check(
        f"[5] provas de inclusao ({len(proofs)} eventos)",
        bad_proofs == 0, f"{bad_proofs} provas invalidas" if bad_proofs else ""))

    # 6. recibos OpenTimestamps
    if check_ots:
        ots_anchors = [a for a in anchors
                       if a["anchor_type"] == "OPENTIMESTAMPS" and a.get("receipt_b64")]
        bad_ots = 0
        confirmed_btc = 0
        skipped = False
        for a in ots_anchors:
            try:
                from opentimestamps.core.serialize import BytesDeserializationContext
                from opentimestamps.core.timestamp import DetachedTimestampFile
                from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
                receipt = base64.b64decode(a["receipt_b64"])
                det = DetachedTimestampFile.deserialize(
                    BytesDeserializationContext(receipt))
                expected_digest = bytes.fromhex(a["merkle_root"].split(":")[1])
                if det.timestamp.msg != expected_digest:
                    bad_ots += 1
                    continue
                if any(isinstance(att, BitcoinBlockHeaderAttestation)
                       for _, att in det.timestamp.all_attestations()):
                    confirmed_btc += 1
            except ImportError:
                results.append(_check("[6] recibos OpenTimestamps", True,
                                      "pulado (pip install opentimestamps)"))
                skipped = True
                break
            except Exception:
                bad_ots += 1
        if not skipped and ots_anchors:
            results.append(_check(
                f"[6] recibos OpenTimestamps ({len(ots_anchors)} .ots, "
                f"{confirmed_btc} confirmados no Bitcoin)",
                bad_ots == 0,
                f"{bad_ots} recibos divergentes" if bad_ots else ""))

    all_ok = all(results)
    n_open = bundle["summary"].get("events_in_open_batch", 0)
    n_conf = sum(1 for a in anchors if a["status"] == "CONFIRMED")
    print()
    print(f"  RESULTADO: {'TRILHA INTEGRA' if all_ok else 'TRILHA COMPROMETIDA'}")
    print(f"  {len(events)} eventos, {len(anchors)} ancoras, "
          f"{n_conf} confirmadas no Bitcoin, {n_open} aguardando proximo lote")
    return all_ok


def verify_legacy(events: list[dict], pubkeys: Optional[dict],
                  root: Optional[str]) -> bool:
    ok_chain, errs = verify_chain(events)
    _check(f"cadeia ({len(events)} eventos)", ok_chain, "; ".join(errs))
    ok_sigs = True
    if pubkeys:
        bad = sum(1 for ev in events
                  if ev.get("agent_sig") and ev.get("agent_id") in pubkeys
                  and not verify_event_signature(
                      ev, ev["agent_sig"], pubkeys[ev["agent_id"]]))
        ok_sigs = bad == 0
        _check("assinaturas", ok_sigs, f"{bad} invalidas" if bad else "")
    ok_root = True
    if root:
        computed = merkle_root([ev["hash"] for ev in events])
        ok_root = computed == root
        _check("raiz Merkle", ok_root, "" if ok_root else f"calc {computed}")
    all_ok = ok_chain and ok_sigs and ok_root
    print(f"\nRESULTADO: {'TRILHA INTEGRA' if all_ok else 'TRILHA COMPROMETIDA'}")
    return all_ok


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="juno-verify")
    p.add_argument("file", help="bundle export.json OU lista de eventos (legacy)")
    p.add_argument("--pubkeys", help="(legacy) {agent_id: chave_publica}")
    p.add_argument("--root", help="(legacy) raiz Merkle esperada")
    p.add_argument("--no-ots", action="store_true",
                   help="nao verifica recibos OpenTimestamps")
    args = p.parse_args(argv)
    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)
    is_bundle = isinstance(data, dict) and data.get(
        "schema_version", "").startswith("juno-audit-export/")
    print(f"\njuno-verify  -  {'bundle' if is_bundle else 'legacy'} mode  -  {args.file}\n")
    if is_bundle:
        ok = verify_bundle(data, check_ots=not args.no_ots)
    else:
        pubkeys = json.load(open(args.pubkeys)) if args.pubkeys else None
        ok = verify_legacy(data, pubkeys, args.root)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
