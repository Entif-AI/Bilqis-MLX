from __future__ import annotations


class SummaryProjection:
    def _cumulative_exam(self, cohort, rubric, scope, step, phase):
        """Show one checkpoint's complete grade-prefix exam, never summed bests."""
        if len(cohort) < 2 or set(cohort) != set(self.grades):
            return
        key = (tuple(sorted(cohort)), rubric, scope)
        correct = sum(score for caps in cohort.values() for score, _ in caps.values())
        total = sum(count for caps in cohort.values() for _, count in caps.values())
        self.board.state["_all_grade_correct"] = correct
        self.board.state["_all_grade_total"] = total
        best = self.cumulative_best.get(key)
        if best is None or correct * best[1] > best[0] * total:
            best = (correct, total, step)
            self.cumulative_best[key] = best
        status = ("PROGRESSION GATE MET / MASTERY DEBT"
                  if phase == "AWAITING_NEXT_GRADE_WITH_DEBT" else
                  "GATE MET" if correct == total and phase in
                  ("AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED") else
                  "REVALIDATION PENDING" if correct == total else
                  f"{total}/{total} REQUIRED")
        self.cumulative_latest = (key, correct, total, step, status)
        label = "+".join(key[0])
        detail = (f"{status} | latest {correct}/{total} | "
                  f"best same student {best[0]}/{best[1]}")
        rows = self.board.rows["SYSTEM & QUALIFICATION"]
        new_row = {"kind": "CUMULATIVE", "grade": label, "detail": detail}
        for index, existing in enumerate(rows):
            if existing["kind"] == "CUMULATIVE":
                rows[index] = new_row
                break
        else:
            rows.append(new_row)

    def _summary(self):
        grade = self.last_exam_grade
        if grade is None:
            return
        reports = [v for (g, _, _), v in self.latest.items() if g == grade]
        report = max(
            reports,
            key=lambda item: (
                item.generation if type(item.generation) is int else -1,
                item.step if type(item.step) is int else -1,
            ),
            default=None,
        )
        if report is None:
            return
        key = (grade, report.rubric, report.assessment_scope)
        start = self.start[key]
        best = self.best[key]
        latest = report
        live = key in self.exam_cohorts
        category = "GENERATED SAMPLE" if live else "SEALED"
        self.board.operator_lines = [
            f"START {category} {grade} {start.correct}/{start.total} @step {start.step or '-'} | "
            f"LATEST {grade} {latest.correct}/{latest.total} @step {latest.step or '-'} | "
            f"{'BEST OBSERVED SAMPLE (not paired)' if live else 'BEST'} {grade} "
            f"{best.correct}/{best.total} @step {best.step or '-'}",
            f"TO100 {latest.total-latest.correct}/{latest.total} wrong ({'fresh sampled cohort' if live else 'sealed rubric'}) | "
            f"Source-train rewards are in-sample; independent sentinel NOT MEASURED",
        ]
        if live:
            count = len(self.era_cohorts.get(key, ()))
            self.board.operator_lines.append(
                f"HISTORY ERA {self.score_era} | {count} cohort{'s' if count != 1 else ''} | "
                f"TOP {best.correct}/{best.total} @step {best.step or '-'} | "
                "cross-cohort context, not a paired delta")
        if self.cumulative_latest is not None:
            key, correct, total, step, status = self.cumulative_latest
            best = self.cumulative_best[key]
            self.board.operator_lines.append(
                f"CUMULATIVE {'+'.join(key[0])}: {status}; latest {correct}/{total} @step {step}; "
                f"best SAME STUDENT {best[0]}/{best[1]} @step {best[2]}. "
                "Individual grade champions are not additive.")
        # A diagnostic observation, not an optimizer signal. Individual
        # source-training measurements may come from different checkpoints.
        families = tuple(latest.capabilities)
        if (not live and latest.correct < latest.total and families and
                all(cap in self.last_source_training and
                    self.last_source_training[cap][0] >= .99 for cap in families)):
            self.board.operator_lines.append(
                f"GENERALIZATION GAP OBSERVED: recent source-train accuracy >=99% "
                f"for {len(families)}/{len(families)} capabilities (different steps); "
                f"{'generated' if live else 'sealed'} {latest.correct}/{latest.total} at one checkpoint")
