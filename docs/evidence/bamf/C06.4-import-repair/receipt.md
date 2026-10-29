# C06.4 — preserve fresh native imports

Status: **IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION**; issue #507 remains open.
Base b04c4181245cb23f7f52f17735618125dde35af3, consumed unified
7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4. IPR-0220.

A C07 source-route test importing the native operating loop in a fresh process
exposed a committed C06.4 regression. Diagnostics eagerly imported the new C06
adapter while teacher_strategy_population was partially initialized through
teacher_feedback. The adapter's teacher selector then re-entered that population
module. Earlier warm import order masked the ImportError.

The public diagnostic facade now defers its implementation import until called;
its signature and result remain unchanged. A fresh-interpreter regression test
imports the native learning_experiment and operating_loop modules separately,
without invoking either trainer or any neural execution.

Red: both subprocess import cases failed. The existing runner subtracts failed
subtests from whole-test counts and prints a negative passed subtotal; that is a
runner reporting artifact, not successful proof. Full raw receipt is retained.
Green: **87 affected tests passed**, zero failures/errors/skips. Independent
fresh-context Goldfish /root/c06_4_fresh_goldfish inspected the small repair,
red evidence and87/87 receipt using Google EGM pin
b3a35956759bf7f024af2ff061b2e0b44b438e4c. PASS; no blocker/major; reviewer
executed no tests. PM-2026-10-29-005 native ledger enriched/read back before repair.

Only this facade, fresh-process test and evidence belong to this repair. Ongoing
uncommitted C07 source edits remain outside the reviewed patch. No actual trainer,
student/own AdamW, graph or accepted generation was read or changed. Earlier
broader diagnostic baseline failures and all real A09/B11/B13/A05-prefix/MLX
requalification obligations remain. PR #550 stays draft and unmerged.
