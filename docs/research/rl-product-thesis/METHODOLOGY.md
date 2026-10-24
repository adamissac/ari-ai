# Read-only feasibility and product-thesis assessment

Scope: retained feasibility001 records only. No environment reset/step, new arrivals,
policy rollout, workload replay, oracle controller, training or checkpoint operation.
The original study is externally anchored at SHA256
931fbd6737f963a1fe661ab029d08b7f4a26fe09e42805c291c9d1a1a2a0246c.
All600 artifact hashes are checked before reading the120 unique noop workload traces.
Repeated policy arms are not counted as independent offered workloads.

For each legitimate request i, archived release r_i, demand p_i and deadline
 d_i=r_i+24 define necessary processing conditions. Physical two-worker supply is
480 worker-ticks during30 decisions, at most48 more during bounded settlement.
Queue capacity12 waiting plus2 in service, FIFO/nonpreemption, per-request execution
speed, rate quotas and collateral constraints remain real restrictions. The bounds
below deliberately relax restrictions, never replace the registered acceptance test.

For interval I=[a,b], J_I contains legitimate jobs with r_i>=a and d_i<=b. Their
work must fit in2(b-a) worker-ticks if completed. Let k_I be the maximum number of
cheapest J_I jobs whose total demand fits. Then maximum legitimate completions
C* <= N-|J_I|+k_I. Minimum over all recorded release/deadline endpoints gives a
rigorous necessary upper bound. Total-demand/cheapest90% work are necessary checks,
not achievable service estimates. An upper bound >=90% does not certify physical,
queue, latency or denial feasibility. No solver optimum or feasible oracle schedule
is claimed. Existing observed completions provide lower witnesses for the completion
objective only; they do not certify the conjunction of safety constraints.

Oracle A: perfect labels, per-request admission, physical restrictions. The computed
interval bound is a relaxation of A; it may overestimate A, not solve A. For A's lower
witness use the largest recorded legitimate completion count across five arms.
Oracle B: exact existing three actions including deterministic previous-work source
selector, one-window delay,two-window duration,cooldown2,budget4,<=64 active ticks.
It is a subset of A's more expressive admission decisions. Its completion upper bound
cannot exceed A's relaxed bound. Valid budgeted-arm traces witness attainable
completion counts but not safe optimality; exclude persistent-static from B witnesses.
No schedule enumeration, MILP, branch-and-bound search or new rollout is authorized.

An additional *offered-work rejection* bound relaxes B further: allow any source or
route1 target, reject all matching adversarial jobs with zero quota leakage/collateral,
and choose any8 windows, ignoring delay,contiguity,cooldown and source observability.
Per window take the largest matching adversarial offered-work scope; sum the top8.
This upper-bounds offered work removable by real controls. The remaining offered
work is not a lower bound on consumed CPU: admission rejection and deadline expiry
can discard work. It cannot prove unachievable legitimate availability.

Oracle C: decisions restricted to actual prior73-channel observations and masks.
The five observed rules do not identify all counterfactual trajectories. No exact
C optimum, learned-policy benefit or impossible-observation theorem is inferred.
Identity overlap is described from labels offline, never exposed to a policy.

Tool budget: one fresh analysis process,60 wall seconds,256MiB measured peak RSS;
fixed engineering ceiling for this read-only computation, not a new study budget.
Source is committed before calculation; output refuses overwrite and retains errors.
No statistical population extrapolation or new bootstrap is performed. Family means
and finite-record bounds describe only the archived120 workloads. Original SLOs and
all600 outcomes remain unchanged. Reproducibility requires the original sealed
input plus the new analysis source commit and output hashes.
