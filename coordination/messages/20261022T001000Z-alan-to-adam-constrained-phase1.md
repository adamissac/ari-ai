# RL-CMDP-001: isolated Phase 1 research foundation

Owner explicitly requested audit, separate measured reward/cost, baseline harness and
architecture decision. Branch `feat/alan/constrained-rl-phase1`, based on main `198eb3b`.
No training run, promotion, production recommendation change or seven-agent integration.

The versioned `ResearchTransition` is a package-internal research adapter, not a new
platform API or canonical experience contract. It reuses canonical `shared.EvidenceRef`.
Fields: source artifact/hash/locator, scenario/hash/split/seed/t, original layout,
observations/current and next mask, action, termination/truncation, measured attack and
benign counts, separated reward=-compromised_reads and cost=benign_blocked, original
scalar reward, explicit unknown delegated cost/behavior propensity. No guessed values.
Unknown measurements require a reason. Initial historical current mask remains unknown.
Only explicit train/validation analysis; never holdout or training consumption.

This adapter stays behind the existing lab artifact boundary pending agreement on a
future shared ExperienceDataset/CMDP contract; no shared schema/TS/API changes now.
No canonical model is duplicated. Adam: review research action-capability profile and
reward/cost units before any future Phase 2. Alan: no seven-agent prose becomes reward.
