;; Mixed instantaneous + durative domain (#84): the instantaneous `plug`
;; enables the durative `charge-battery`. Instantaneous actions participate in
;; the schedule as zero-duration steps.
(define (domain charge)
  (:requirements :strips :typing :durative-actions)
  (:types device)
  (:predicates
    (plugged ?d - device)
    (unplugged ?d - device)
    (charged ?d - device))

  (:action plug
    :parameters (?d - device)
    :precondition (unplugged ?d)
    :effect (and (not (unplugged ?d)) (plugged ?d)))

  (:durative-action charge-battery
    :parameters (?d - device)
    :duration (= ?duration 4)
    :condition (and (at start (plugged ?d))
                    (over all (plugged ?d)))
    :effect (at end (charged ?d))))
