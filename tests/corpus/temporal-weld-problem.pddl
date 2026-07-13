;; Solvable: torch is lit, so steady-weld's 'at end (torch-lit)' holds.
(define (problem weld-p1)
  (:domain weld)
  (:objects p1 - part)
  (:init (holding p1) (torch-lit))
  (:goal (welded p1)))
