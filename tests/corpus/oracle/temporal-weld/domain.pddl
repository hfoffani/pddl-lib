;; Temporal demonstrator (#84): 'over all' genuinely constrains the plan.
;;
;; Both welds are applicable *at start* (they only need a held part), so an
;; at-start-only checker would happily emit the cheaper `quick-weld`. But
;; quick-weld lets go of the part *at start* while its own 'over all' invariant
;; demands the part stay held for the whole duration — so it is never actually
;; executable. Only `steady-weld`, which keeps holding the part until the end,
;; yields a valid schedule (makespan 6).
(define (domain weld)
  (:requirements :strips :typing :durative-actions)
  (:types part)
  (:predicates
    (holding ?p - part)
    (welding ?p - part)
    (welded ?p - part)
    (torch-lit))

  ;; Drops the clamp at start -> violates its own 'over all (holding)'.
  (:durative-action quick-weld
    :parameters (?p - part)
    :duration (= ?duration 2)
    :condition (and (at start (holding ?p))
                    (over all (holding ?p))
                    (at end (torch-lit)))
    :effect (and (at start (not (holding ?p)))
                 (at end (welded ?p))))

  ;; Keeps holding the part across the interval; releases only at end.
  (:durative-action steady-weld
    :parameters (?p - part)
    :duration (= ?duration 6)
    :condition (and (at start (holding ?p))
                    (over all (holding ?p))
                    (at end (torch-lit)))
    :effect (and (at start (welding ?p))
                 (at end (not (welding ?p)))
                 (at end (welded ?p))
                 (at end (not (holding ?p))))))
