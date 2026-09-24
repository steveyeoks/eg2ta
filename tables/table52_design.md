**Table 5.2. The experimental design, one row per problem; the models are the panels of Figure 5.1 and the expected verdicts are those of expected.json.**

| problem | EG-TCTL | UPPAAL | model: expected |
|---|---|---|---|
| ACCESSIBILITY | $\exists\Diamond\, q_n = 2$ | `E<> (SU.wait && qn == 2)` | (a), $n = 1, 2, 3$: SAT |
| ORDERING | $\exists\Diamond\, P_1$, $\exists\Diamond\, P_2$ | `E<> (SU.wait && P1)`, `E<> (SU.wait && P2)` | (d) under $\succ_1$: SAT, UNSAT. Under $\succ_2$: UNSAT, SAT |
| NONINTERCHANGEABILITY | $(q_1 \ge 1 \wedge a_1 \ge 1) \rightsquigarrow (q_1 = 0 \vee a_1 = 0)$ | `(SU.wait && (q1 >= 1 && a1 >= 1)) --> (SU.wait && (q1 == 0 \|\| a1 == 0))` | (b): SAT. (c): UNSAT. $n = 1, 2, 3$ |
| STALLING | $\exists\Diamond\,(\mathrm{FEL} = \emptyset \wedge \mathrm{dep} < 3)$ | `E<> (SU.wait && idle && dep < 3)` | (b): UNSAT. (c): SAT. $n = 1, 2, 3$ |
