# Changelog

All notable changes are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions will follow
[Semantic Versioning](https://semver.org/) once releases begin.

## [Unreleased]



- Fix live-layout recommendation serving: load checkpoints without lab dependencies, explain the policy-selected action after abstention, keep Q confidence metadata ranked, and avoid inferring training origin from checkpoint layout.

- Contracts 0.13 (additive): `DefenseActionName` gains `block_principal_long` and `block_top_principal_long`, and `PlatformFacts` gains the live v3 detector fields (defaults keep old payloads valid). The schema bump also covers `block_principal` (#324) and the principal-block fields (#334). `PolicyRunner` can now serve live v3 checkpoints as lab-scoped recommendations. Inference no longer imports the live lab.
