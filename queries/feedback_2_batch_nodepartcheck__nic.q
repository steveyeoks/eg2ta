// work conservation at station 2 (Depart->Start2 missing)
(SU.wait && (q2 >= 1 && a2 >= 1)) --> (SU.wait && (q2 == 0 || a2 == 0))
