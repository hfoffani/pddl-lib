(define (domain da)
 (:requirements :strips :typing :durative-actions)
 (:types loc)
 (:predicates (at ?l - loc) (visited ?l - loc))
 (:durative-action go
   :parameters (?from - loc ?to - loc)
   :duration (= ?duration 5)
   :condition (at start (at ?from))
   :effect (and (at start (not (at ?from))) (at end (at ?to)) (at end (visited ?to)))))
