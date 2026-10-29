;; Solvable: plug the phone (t=0), then charge it (t=0..4). Makespan 4.
(define (problem charge-phone)
  (:domain charge)
  (:objects phone - device)
  (:init (unplugged phone))
  (:goal (charged phone)))
