; Plan validation probes (roadmap step 3): temporal semantics.
; tests/test_oracle.py checks that VAL gives the verdicts that
; tests/test_validation.py expects.
(define (domain probe-temporal)
  (:requirements :durative-actions :negative-preconditions)
  (:predicates (p) (q) (r) (s))
  (:durative-action a :parameters () :duration (= ?duration 2)
    :condition (at start (p))
    :effect (at end (q)))
  (:durative-action b :parameters () :duration (= ?duration 3)
    :condition (and (at start (q)) (over all (q)) (at end (not (s))))
    :effect (at end (r)))
  (:durative-action c :parameters () :duration (= ?duration 1)
    :condition (at start (p))
    :effect (at start (s)))
  (:durative-action k :parameters () :duration (= ?duration 1)
    :condition (at start (p))
    :effect (at end (not (q))))
  (:action tick :parameters () :precondition (p) :effect (s)))
