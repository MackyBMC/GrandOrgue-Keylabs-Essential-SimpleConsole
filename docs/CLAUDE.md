# docs/ rules
- Start at `README.md` (map and status tags). Do not duplicate content between documents; link.
- Every statement about the real organ/hardware carries VERIFIED or UNVERIFIED (see GUARDRAILS I-8).
- Architectural change = new or superseding ADR in `adr/`. Never edit an ACCEPTED ADR in place.
- When code changes a contract, invariant, file location, channel plan or port name, update the matching document in the same patch (INFRASTRUCTURE, CONTRACTS, GUARDRAILS, INVENTORY-V2).
- Update the "Document history" table in README.md and keep the changelog habit: newest first, dated.
- Questions for the owner go in `claude.chat/<patch-name>.txt`, not in chat.
- `HANDOFF.md` and `NEXT-SESSION.md` describe the v2.0.x working state; do not rewrite them for v3, add v3 material to the documents in README.md.
