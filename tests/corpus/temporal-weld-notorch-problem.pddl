;; Unsolvable: no lit torch, so steady-weld's 'at end (torch-lit)' condition
;; fails and quick-weld self-violates its 'over all' -- no valid schedule.
(define (problem weld-notorch)
  (:domain weld)
  (:objects p1 - part)
  (:init (holding p1))
  (:goal (welded p1)))
