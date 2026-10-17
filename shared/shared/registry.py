"""Every exported contract model, in a stable order (drives schema/TS generation)."""

from __future__ import annotations

from pydantic import BaseModel

from shared import (
    api,
    assessment,
    audit,
    errors,
    events,
    evidence,
    findings,
    intelligence,
    intelligence_memory,
    monitoring,
    review,
    rl,
    scope,
    tenancy,
)

MODELS: tuple[type[BaseModel], ...] = (
    # errors / evidence
    errors.ErrorBody,
    errors.ErrorResponse,
    evidence.SourceSpan,
    evidence.EvidenceRef,
    evidence.ArtifactRef,
    # tenancy
    tenancy.Budget,
    tenancy.Usage,
    tenancy.TriggerPolicy,
    tenancy.ProjectSettings,
    tenancy.Organization,
    tenancy.User,
    tenancy.Membership,
    tenancy.Project,
    tenancy.Repository,
    # scope
    scope.ScopeTarget,
    scope.AuthorizedScope,
    scope.Approval,
    # intelligence
    intelligence.SnapshotRef,
    intelligence.SnapshotStats,
    intelligence.Snapshot,
    intelligence.Symbol,
    intelligence.CallEdge,
    intelligence.EntryPoint,
    intelligence.BehavioralExpectation,
    intelligence.ContextPackRequest,
    intelligence.ContextChunk,
    intelligence.ContextPack,
    intelligence.ImpactSet,
    intelligence_memory.ExpectationDecisionRequest,
    intelligence_memory.ExpectationDecision,
    intelligence_memory.VerifiedRegression,
    # assessment / agents
    assessment.Assessment,
    assessment.ToolCallRecord,
    assessment.AgentRun,
    assessment.AgentStepInput,
    assessment.AgentStepResult,
    # findings chain
    findings.SeverityFactors,
    findings.SeverityAssessment,
    findings.StatusChange,
    findings.Finding,
    findings.Hypothesis,
    findings.ValidationResult,
    findings.PathStep,
    findings.AttackPath,
    findings.RootCause,
    findings.RemediationPlan,
    findings.PatchCandidate,
    findings.VerificationCheck,
    findings.VerificationResult,
    findings.HardeningRecommendation,
    # review
    review.ChangeIntent,
    review.IntentClaim,
    review.IntentEvidence,
    review.ReviewRequest,
    review.GeneratedTest,
    review.ReviewResult,
    # monitoring
    monitoring.CommitRange,
    monitoring.MonitoringEvent,
    monitoring.ReassessmentRequest,
    monitoring.RouteWindow,
    monitoring.RuntimeSignalBatch,
    monitoring.RouteScore,
    monitoring.RuntimeIngestAck,
    monitoring.IngestTokenCreated,
    # rl
    rl.NodeSignals,
    rl.PlatformFacts,
    rl.ActionScore,
    rl.DefenseRecommendation,
    rl.RLCheckpointRef,
    rl.RLEvaluation,
    rl.FeatureContribution,
    rl.RLExplanation,
    # audit / events
    audit.AuditEvent,
    events.StreamEvent,
    # api DTOs
    api.HealthStatus,
    api.ReadinessStatus,
    api.MembershipView,
    api.MeResponse,
    api.DevLoginRequest,
    api.ProjectCreate,
    api.ProjectUpdate,
    api.RepositoryConnect,
    api.SnapshotCreate,
    api.ScopeCreate,
    api.ApprovalDecision,
    api.AssessmentCreate,
    api.AcceptRisk,
    api.AssessmentDetail,
    api.PatchView,
    api.WebhookAck,
)

BY_NAME: dict[str, type[BaseModel]] = {m.__name__: m for m in MODELS}
assert len(BY_NAME) == len(MODELS), "duplicate contract model names"
