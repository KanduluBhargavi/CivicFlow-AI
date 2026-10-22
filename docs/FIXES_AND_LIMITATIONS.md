# CivicFlow stability repairs

- Incident authors automatically count as affected once per unique citizen; no extra support click.
- Incident details timeout, retry and helpful empty/error state rather than infinite loading.
- Frontend submission locked during request; server rejects sequential identical submission within two minutes. Concurrent submissions still need transactional idempotency for guaranteed protection.
- Conservative water outage vs contamination semantic-compatibility guard. Historic incident clusters may need independent auditing/reclustering.
- A maximum of three citizen reopen requests, counted from persistent events. Citizens may request independent review; satisfaction is not fabricated.
- Photo attestation, JPEG/PNG format verification and 24MP limit, MP4 signature sanity check. This does NOT identify irrelevant photo content; human review or tested CV is required.
- Bhashini remains pending approval.
- Back up current working project before replacing files.
