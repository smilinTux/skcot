# Where skcot lands in the stack

This is the dependency doc. It states the facts precisely, because "what does this thing require" is exactly the question that gets fuzzy once a package has been around for a while. skcot has a deliberately small answer.

## The one hard dependency

skcot depends on exactly one package: **skcomms**, the sovereign messaging fabric. That is the complete dependency surface. skcot imports the following skcomms modules:

- `skcomms.core`
- `skcomms.discovery`
- `skcomms.envelope`
- `skcomms.home`
- `skcomms.identity`
- `skcomms.tofu`

Nothing else. skcot does not require, import, or assume the presence of `skcapstone`, `skchat`, or `cloud9`.

## skcapstone is optional

`skcapstone` is the agent framework: identity, memory, the consciousness loop that gives an AI its "brain." Run skcot alongside skcapstone and the AI teammate on the tactical net has real reasoning and memory driving what it beacons and what it says back in GeoChat.

Without skcapstone, skcot still runs. It works as a standalone CoT/TAK bridge plus situational store:

- it ingests operator CoT from connected ATAK/iTAK/WinTAK devices,
- it federates that CoT to peer nodes over the skcomms fabric,
- it maintains the situational picture in `GEO_STORE` (nearest-neighbor queries, summaries, GeoJSON),
- it can still beacon a position.

It just is not being driven by an AI agent's reasoning in that mode. The wire, the picture, and the position beacon all work on their own; the "teammate that thinks and answers" layer is what skcapstone adds on top.

## The layering, bottom to top

```
skcomms   (fabric: identity, envelopes, discovery, trust-on-first-use)   REQUIRED
   |
   v
skcot     (tactical CoT/TAK leaf: streaming endpoint, GEO_STORE, PKI, agent)
   |
   v
skcapstone (OPTIONAL: the AI brain, memory, and consciousness loop on top)
```

skcot is a thin leaf on skcomms. It is close to standalone: one required dependency below it, one optional consumer above it, and nothing else in between.

## Dependency table

| Package | Role | Required? |
|---|---|---|
| skcomms | Sovereign messaging fabric: envelopes, identity, discovery, trust-on-first-use. skcot's transport and federation layer. | Yes, the only hard dependency |
| takproto | TAK Protocol protobuf codec for the mesh (Mesh SA) path. | No, optional extra: `skcot[tak]` |
| skcapstone | Agent framework: identity, memory, the consciousness loop. Drives the AI teammate's reasoning and replies. | No, optional, runs alongside |
| skchat | Chat interface. | No, not a dependency |
| cloud9 | Emotional continuity protocol. | No, not a dependency |

## The one-way rule

skcot depends on skcomms. skcomms never depends on skcot. This holds in both directions of the codebase: skcomms has no import of, or awareness of, anything in skcot. The boundary is testable by grepping either tree for a reference to the other; skcomms should come back empty every time.

This one-way rule is what keeps skcot a leaf instead of a tangle. skcomms stays a general-purpose fabric usable by anything (skchat, skcapstone, or a package that has not been written yet); skcot is one specific tenant of that fabric, free to change its own internals (codec formats, the situational store's schema, the PKI layout) without ever touching skcomms.

## Optional extra: TAK Protocol support

ATAK's "Mesh SA" traffic can ride the wire as legacy CoT XML or as TAK Protocol protobuf. skcot handles both, but the protobuf path needs the `takproto` library. Install it with:

```bash
pip install -e "skcot[tak]"
```

Without the `[tak]` extra, skcot still runs the full TCP, TLS, and XML mesh paths; only the protobuf mesh codec needs `takproto` in the environment.
