# Architecture deep dives

Status: **specified**. Overview first: [04 System architecture](../04_SYSTEM_ARCHITECTURE.md).

| Doc | Covers |
|---|---|
| [system-context](system-context.md) | C4 level 1–2: actors, external systems, containers |
| [code-intelligence](code-intelligence.md) | Indexing pipeline internals, storage, retrieval, incremental updates |
| [assessment-lifecycle](assessment-lifecycle.md) | End-to-end sequence of one assessment, artifacts per step |
| [sandbox-and-authorization](sandbox-and-authorization.md) | Scope guard, tool registry, sandbox driver, network modes |
| [event-lifecycle](event-lifecycle.md) | Webhook/runtime event → impact → re-assessment |
| [rl-training-and-inference](rl-training-and-inference.md) | RL env, training jobs, checkpoints, recommendation path |
| [data-flow-and-storage](data-flow-and-storage.md) | Tables, artifact store, retention, what is untrusted |
| [deployment-topology](deployment-topology.md) | Local/demo topology and the hosted option |
| [seven-agent-rl-adversarial-integration](seven-agent-rl-adversarial-integration.md) | **Design only (gated):** how the seven-agent offensive pipeline would feed the RL defender — schemas, seams, constraints |
